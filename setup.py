import io
from setuptools import setup, find_packages




setup(name='vts_bruh',
      description=u"Mapbox Vector Tile",
      long_description='vts',
      classifiers=[],
      keywords='',
      license='MIT',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite="setup.test_suite",
      install_requires=["setuptools", "protobuf", "future"]
      )
