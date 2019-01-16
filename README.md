# NETCONF/YANG Test Framework


This repository homes two distinct but related projects:

## Connector

The ``yang.connector`` module features a series of classes that connect to Data Model Interfaces (DMI), 
in particular, an implementation of NETCONF client. It is designed to be the de-facto NETCONF connection implementation
for Cisco [pyATS](https://developer.cisco.com/site/pyats/).

See [Connector Documentation](/connector/docs/README.rst) for more details.

## Ncdiff

``yang.ncdiff`` module features classes that allows the user to download, compile, and diff NETCONF configs for automation
purposes, such as calculating new config states based on current configuration state, and any new edit-configs. 

See [Ncdiff Documentation](/ncdiff/docs/README.rst) for more details.


## Installation

Both packages are featured Python Package Index, and can be directly installed into your Python environment.

```bash
# connector
pip install yang.connector

# ncdiff
pip install yang.ncdiff

```

## Support

Everyone is welcomed to contribute to this git repository. For support questions and issues, open an issue under this
git repository and it will be attended to. 
