import setuptools

with open("./README.md", 'r') as f:
    long_description = f.read()

with open('./requirements.txt', 'r') as f:
    requirements = [a.strip() for a in f]

setuptools.setup(
    name="wsmprpc",
    version="1.1.0",
    author="Huang Yan",
    author_email="hyansuper@foxmail.com",
    description="python msgpack RPC over websocket",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hyansuper/wsmprpc",
    packages=['wsmprpc'],
    install_requires=requirements,
    classifiers=(
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)