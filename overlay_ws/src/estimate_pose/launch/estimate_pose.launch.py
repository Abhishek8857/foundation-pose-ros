from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([Node(
        package='estimate_pose',
        executable='estimate_pose',
        name='foundation_pose_node',
        output='screen',
        parameters=[{
                'mesh_path': '/workspace/cnos-ros/cnos/templates/cube.obj',
                'rgb_topic': '/front_stereo_camera/rgb/image_raw',
                'depth_topic': '/front_stereo_camera/depth/image_rect_raw',
                'camera_info_topic': '/front_stereo_camera/rgb/camera_info',
                'est_refine_iter': 5,
                'track_refine_iter': 5,
                }],
    )])
    
