import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='os_market',
    version='0.1',
    scripts=[] ,
    author="",
    author_email="",
    description="Twisted pusher",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/socillion/twistedpusher",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Operating System :: Linux",
    ],
)
