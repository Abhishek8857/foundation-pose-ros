#!/usr/bin/env python3
import os
import sys
import cv2
import trimesh
import threading
import traceback
import numpy as np
import nvdiffrast.torch as dr
import rclpy
from scipy.spatial.transform import Rotation as R
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

from cv_bridge import CvBridge
from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import PoseStamped
from pose_est_interface.srv import EstimatePose
from estimater import FoundationPose, ScorePredictor, PoseRefinePredictor
from Utils import draw_posed_3d_box, draw_xyz_axis


class FoundationPoseNode(Node):
    def __init__(self):
        super().__init__("foundation_pose_node")
        
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        
        self.latest_rgb = None
        self.latest_depth = None
        self.K = None
        self._registered = False
        self.latest_vis = None 
        self.create_timer(0.03, self.show_loop)
        
        # Parameters
        self.mesh_path = self.declare_parameter('mesh_path', '/workspace/cnos-ros/cnos/templates/cube.obj').value
        self.rgb_topic = self.declare_parameter('rgb_topic', '/front_stereo_camera/rgb/image_raw').value
        self.depth_topic = self.declare_parameter('depth_topic', '/front_stereo_camera/depth/image_rect_raw').value
        self.camera_info_topic = self.declare_parameter('camera_info', '/front_stereo_camera/rgb/camera_info').value
        self.est_refine_iter = self.declare_parameter('est_refine_iter', 5).value
        self.track_refine_iter = self.declare_parameter('track_refine_iter', 5).value
        self.show_window = self.declare_parameter('show_window', True).value
        
        # Mesh 
        self.get_logger().info(f"Loading Mesh: {self.mesh_path}")
        
        try:   
            self.mesh = trimesh.load(self.mesh_path)
        except Exception as e:
            self.get_logger().info(f"Could not load mesh: {e}")

        # Set bounding box for visualisation
        self.to_origin, extents = trimesh.bounds.oriented_bounds(self.mesh)
        self.bbox = np.stack([-extents / 2, extents / 2], axis=0).reshape(2, 3)

        # Load Foundation pose
        self.get_logger().info("Loading Foundation Pose")

        scorer = ScorePredictor()
        refiner = PoseRefinePredictor()
        glctx = dr.RasterizeCudaContext()

        self.estimator = FoundationPose(
                    model_pts=self.mesh.vertices,
                    model_normals=self.mesh.vertex_normals,
                    mesh=self.mesh,
                    scorer=scorer,
                    refiner=refiner,
                    glctx=glctx,
                )
        
        self.get_logger().info("Foundation Pose Ready")
        
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        
        # Create Subscriptions
        self.create_subscription(Image, self.rgb_topic, self.rgb_callback, qos)
        self.create_subscription(Image, self.depth_topic, self.depth_callback, qos)
        self.create_subscription(CameraInfo, self.camera_info_topic, self.camera_info_callback, qos)
        self.get_logger().info(f"Subscribed to RGB: {self.rgb_topic}, Depth: {self.depth_topic}, K: {self.camera_info_topic}")
        
        # Create Service
        self.srv = self.create_service(EstimatePose, '/foundation_pose/estimate_pose', self.estimate_pose)
        self.get_logger().info("Service /foundation_pose/estimate_pose/ ready")
        
    
    def rgb_callback(self, msg):
        with self.lock:
            self.latest_rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')
    
    def depth_callback(self, msg):
        with self.lock:
            depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
            self.latest_depth = depth.astype(np.float32)
            if msg.encoding in ('16UC1', 'mono16'):
                self.latest_depth /= 1000.0
    
    def camera_info_callback(self, msg):
        if self.K is None:
            self.K = np.array(msg.k).reshape(3, 3)
            self.get_logger().info(f"Camera intrinsics received:\n{self.K}")
    
    def visualize(self, rgb, K, pose):
        try:
            center_pose = pose @ np.linalg.inv(self.to_origin)

            vis = draw_posed_3d_box(
                K, img=rgb.copy(),
                ob_in_cam=center_pose,
                bbox=self.bbox
            )

            vis = draw_xyz_axis(
                vis,
                ob_in_cam=center_pose,
                scale=0.1,
                K=K,
                thickness=3,
                transparency=0,
                is_input_rgb=True
            )

            self.latest_vis = vis[..., ::-1].copy()

        except Exception:
            self.get_logger().warn(
                f"Visualization failed:\n{traceback.format_exc()}"
            )

    def show_loop(self):
        if self.show_window and self.latest_vis is not None:
            cv2.imshow('foundation_pose', self.latest_vis)
        if self.show_window:
            cv2.waitKey(1)

            
    def estimate_pose(self, request, response):
        with self.lock:
            if self.latest_rgb is None or self.latest_depth is None or self.K is None:
                response.success = False
                response.message = "Missing RGB, depth or camera_info"
                return response
            rgb = self.latest_rgb.copy()
            depth = self.latest_depth.copy()
            K = self.K.copy()
            
        mask = self.bridge.imgmsg_to_cv2(request.mask, desired_encoding='mono8')
        mask_bool = mask.astype(bool)
        
        try:
            if not self._registered:
                self.get_logger().info("Running register()")
                pose = self.estimator.register(
                    K=K, rgb=rgb, depth=depth, ob_mask=mask_bool,
                    iteration=self.est_refine_iter,
                )
                self._registered = True
            else:
                pose = self.estimator.track_one(
                    rgb=rgb, depth=depth, K=K,
                    iteration=self.track_refine_iter,
                )
        except Exception as e:
            self.get_logger().error(f"Pose estimation failed: {e}")
            response.success = False
            response.message = str(e)
            return response
        
        self.visualize(rgb, K, pose)
        
        quat = R.from_matrix(pose[:3, :3]).as_quat()         
        pose_msg = PoseStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = 'camera_frame'
        pose_msg.pose.position.x = float(pose[0, 3])
        pose_msg.pose.position.y = float(pose[1, 3])
        pose_msg.pose.position.z = float(pose[2, 3])
        pose_msg.pose.orientation.x = quat[0]
        pose_msg.pose.orientation.y = quat[1]
        pose_msg.pose.orientation.z = quat[2]
        pose_msg.pose.orientation.w = quat[3]

        response.pose = pose_msg
        response.success = True
        response.message = "OK"
        return response

    
def main():
    rclpy.init()
    node = FoundationPoseNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__== '__main__':
    main()