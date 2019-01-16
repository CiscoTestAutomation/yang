[![published](https://static.production.devnetcloud.com/codeexchange/assets/images/devnet-published.svg)](https://developer.cisco.com/codeexchange/github/repo/CiscoTestAutomation/yang)

# NETCONF/YANG Test Framework


This repository homes two distinct but related packages:

## Connector

The ``yang.connector`` package features a series of classes that connect to Data Model Interfaces (DMI), 
in particular, an implementation of NETCONF client. It is designed to be the de-facto NETCONF connection implementation
for Cisco [pyATS](https://developer.cisco.com/site/pyats/).

See [Connector Documentation](/connector/docs/README.rst) for more details.

## Ncdiff

The ``yang.ncdiff`` package features classes that allows the user to download, compile, and diff NETCONF configs for automation
purposes, such as calculating new config states based on current configuration state, and any new edit-configs. 

See [Ncdiff Documentation](/ncdiff/docs/README.rst) for more details.


## Installation

Both packages are featured in the [Python Package Index](https://pypi.org/) and can be directly installed into your Python environment.

```bash
# connector
pip install yang.connector

# ncdiff
pip install yang.ncdiff

```

## Support

Everyone is welcomed to contribute to this git repository. For support questions and issues, open an issue under this
git repository and it will be attended to. 

> Copyright (c) 2018 Cisco Systems, Inc. and/or its affiliates