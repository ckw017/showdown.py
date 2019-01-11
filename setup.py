import setuptools

with open('README.md', 'r') as readme:
    long_desc = readme.read()

with open('requirements.txt', 'r') as reqf:
    requirements = reqf.read().splitlines()

setuptools.setup(
    name='showdownpy',
    version='0.0.3',
    author='Chris K. W.',
    author_email='chriskw.xyz@gmail.com',
    description='An extendable client for interacting with Pokemon Showdown',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    url='',
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python 3.5+",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
)
