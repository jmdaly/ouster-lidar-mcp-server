from setuptools import setup, find_packages

setup(
    py_modules=["main", "app_setup", "scan_operations", "sensor_operations", "visualization", "test_client", "test_tools"],
    package_dir={"": "."},
)
