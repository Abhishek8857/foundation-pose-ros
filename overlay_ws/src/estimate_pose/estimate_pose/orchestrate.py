import rclpy
from rclpy.node import Node 
from pose_est_interface.srv import Segment, EstimatePose 
import time 

class OrchestratorNode(Node):
    def __init__(self):
        super().__init__('orchestrator_node')
        
        # Segmeantation client
        self.sgmt_client = self.create_client(Segment, '/cnos/segment')
        # Pose Estimation client 
        self.estmt_client = self.create_client(EstimatePose, '/foundation_pose/estimate_pose')
        
        self.get_logger().info("Orchestrator initialized!")
        self.orchestrate()
        
    def orchestrate(self):
        """Execute segmentation and then estimate the pose"""
        
        self.get_logger().info("Waiting for Segmentation service...")
        if not self.sgmt_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().info("Segmentation service failed to initialize.")
            return 
        
        self.get_logger().info("Waiting for Pose Estimation Service...")
        if not self.estmt_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().info("Pose Estimation Service failed to initialize.")
            return
        
        # Segment
        self.get_logger().info("Starting Segmentation...")
        sgmt_req = Segment.Request()
        sgmt_future = self.sgmt_client.call_async(sgmt_req)
        
        rclpy.spin_until_future_complete(self, sgmt_future)
        
        if sgmt_future.result() is None:
            self.get_logger().error(f"Segmentation service call failed: {sgmt_future.exception()}")
            return
        
        sgmt_result = sgmt_future.result()
        
        if not sgmt_result.success:
            self.get_logger().error(f"Segmentation failed: {sgmt_result.message}")
            return 
        
        self.get_logger().info(f"Segmentation succeeded: {sgmt_result.message}")
                
        # Estimate Pose 
        self.get_logger().info("Estimating Pose...")
        est_pose_req = EstimatePose.Request()
        est_pose_req.mask = sgmt_result.mask
        
        est_pose_future = self.estmt_client.call_async(est_pose_req)
        
        rclpy.spin_until_future_complete(self, est_pose_future)
        
        if est_pose_future.result() is None:
            self.get_logger().error(f"Pose Estimation service call failed: {est_pose_future.exception()}")
            return 
        
        est_pose_result = est_pose_future.result()
        
        if not est_pose_result.success:
            self.get_logger().error(f"Pose Estimation failed: {est_pose_result.message}") 
            return
        
        self.get_logger().info("Pose Estimation Succeeded")
        self.get_logger().info(f"Estimated Pose: {est_pose_result.pose}")

def main(args=None):
    rclpy.init(args=args)
    node = OrchestratorNode()
    try: 
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
                
if __name__ == "__main__":
    main()