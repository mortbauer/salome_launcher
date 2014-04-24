from setuptools import setup
setup(
    name='salome_launcher',
    description='easy salome launcher',
    license='LGPL',
    version = 0.0,
    author = 'Martin Ortbauer',
    author_email = 'mortbauer@gmail.com',
    url='http://github/mortbauer',
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: LGPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development',
        ],
    py_modules=['salome_launcher','setenv','salome_utils'],
    platforms='any',
    entry_points = {
        'console_scripts' :[
            'salome_launcher = salome_launcher:dispatch',
        ]},
    )
