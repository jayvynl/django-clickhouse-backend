from pathlib import Path

from setuptools import setup, find_packages


def read(name):
    with open((Path(__file__).parent / name)) as file:
        return file.read()


setup(
    name="django-clickhouse-backend",
    version=read("clickhouse_backend/VERSION").strip(),
    description="Django clickHouse database backend.",
    packages=find_packages(),
    include_package_data=True,
    url="https://github.com/jayvynl/django-clickhouse-backend",
    author="Lin Zhiwen",
    author_email="zhiwenlin1116@gmail.com",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    license="MIT",
    keywords='Django ClickHouse database backend engine driver',
    python_requires='>=3.6, <4',
    install_requires=[
        "django>=3.2",
        "clickhouse-driver==0.2.5",
        "clickhouse-pool==0.5.3",
    ],
    classifiers=[
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ]
)
