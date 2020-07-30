from setuptools import setup, find_packages
from os import path

from io import open

from ehpp.consts import VERSION

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ehpp',
    version=VERSION,
    description='EspHomePreprocessor (EHPP) is a preprocessor for EspHome',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/AlexDanault/EspHomePreprocessor',
    author='Alexandre Danault',
    author_email='alexandre@danault.net',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Home Automation',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords=['home', 'automation', 'esphome',
              'esphomeyaml', 'preprocessor', 'home-assistant'],
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    python_requires='>=3.0, <4',
    install_requires=['pyyaml>=3.12', 'colorama>=0.4.1'],
    entry_points={
        'console_scripts': [
            'ehpp = ehpp.__main__:main'
        ]
    },
    project_urls={
        'Bug Reports': 'https://github.com/AlexDanault/EspHomePreprocessor/issues',
        'Source': 'https://github.com/AlexDanault/EspHomePreprocessor',
    },
)
