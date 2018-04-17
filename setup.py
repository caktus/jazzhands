from setuptools import setup

setup(name='jazzhands',
      version='0.1',
      description='Automagickically build frontend parts of python web projects',
      url='',
      author='Calvin Spealman',
      author_email='calvin@caktusgroup.com',
      license='MIT',
      packages=['jazzhands'],
      zip_safe=False,
      entry_points={
            'console_scripts': [
                  'jazzhands=jazzhands.__main__:main',
            ],
      },
)