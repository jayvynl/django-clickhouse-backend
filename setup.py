from pathlib import Path

from setuptools import setup, find_packages


def read(name):
    with open((Path(__file__).parent / name)) as file:
        return file.read()


setup(
    name='django-clickhouse-backend',
    version=read('clickhouse_backend/VERSION').strip(),
    description='Django clickHouse database backend.',
    packages=find_packages(),
    include_package_data=True,
    url='https://github.com/jayvynl/django-clickhouse-backend',
    author='Lin Zhiwen',
    author_email='zhiwenlin1116@gmail.com',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    license='MIT',
    install_requires=[
        'django>=3.2',
        'clickhouse-driver==0.2.4',
        'clickhouse-pool==0.5.3',
    ],
)
