###############################################################################
#                            yang Internal Makefile
#
# Author:
#   Jonathan Yang (yuekyang) - CSG Polaris DMI Infra
#
# Support:
#	yang-python@cisco.com
#
# Version:
#   v1.0
#
# Date:
#   June 2016
#
# About This File:
#   This script will build the dyntopo package for distribution in PyPI server
#
# Requirements:
#	1. Module name is the same as package name.
#	2. setup.py file is stored within the module folder
###############################################################################

# Variables
PKG_NAME      = yang.connector
BUILDDIR      = $(shell pwd)/__build__
PROD_USER     = pyadm@pyats-ci
PROD_PKGS     = /auto/pyats/packages
STAGING_PKGS  = /auto/pyats/staging/packages
STAGING_EXT_PKGS  = /auto/pyats/staging/packages_external
PYTHON        = python3
TESTCMD       = cd tests; runAll
DISTDIR       = $(BUILDDIR)/dist

DEPENDENCIES = "paramiko >= 1.15.1" "lxml >= 3.3.0, <5.0.0" \
				"ncclient >= 0.6.6" grpcio protobuf


.PHONY: clean package distribute distribute_staging distribute_staging_external\
        develop undevelop populate_dist_dir help docs distribute_docs test

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo ""
	@echo "package                       : Build the package"
	@echo "test                          : Test the package"
	@echo "distribute                    : Distribute the package to PyPi server"
	@echo "distribute_staging            : Distribute the package to staging area"
	@echo "distribute_staging_external   : Distribute the package to external staging area"
	@echo "clean                         : Remove build artifacts"
	@echo "develop                       : Build and install development package"
	@echo "undevelop                     : Uninstall development package"
	@echo "html                          : Build Sphinx documentation for this package"

html:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building $(PKG_NAME) documentation for preview: $@"
	@echo ""

	@sphinx-build -b html -c docs -d ./__build__/documentation/doctrees docs/ ./__build__/documentation/html

	@echo "Completed building docs for preview."
	@echo ""
	@echo "Done."
	@echo ""

test:
	@$(TESTCMD)

package:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building $(PKG_NAME) distributable: $@"
	@echo ""

	@$(PYTHON) setup.py bdist_wheel --dist-dir=$(DISTDIR)
	@$(PYTHON) setup.py sdist --dist-dir=$(DISTDIR)

	@echo "Completed building: $@"
	@echo ""
	@echo "Done."
	@echo ""

develop:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building and installing $(PKG_NAME) development distributable: $@"
	@echo ""

	@pip3 uninstall -y yang.connector || true
	@pip install $(DEPENDENCIES)
	@pip install -e . --no-deps

	@echo "Completed building and installing: $@"
	@echo ""
	@echo "Done."
	@echo ""

undevelop:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Uninstalling $(PKG_NAME) development distributable: $@"
	@echo ""

	@pip uninstall $(PKG_NAME) -y

	@echo "Completed uninstalling: $@"
	@echo ""
	@echo "Done."
	@echo ""

clean:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Removing make directory: $(BUILDDIR)"
	@rm -rf $(BUILDDIR)
	@echo "Removing build artifacts ..."
	@$(PYTHON) setup.py clean
	@echo ""
	@echo "Done."
	@echo ""

distribute:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(PROD_PKGS)"
	@test -d $(BUILDDIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(PROD_PKGS)/$(PKG_NAME) || mkdir $(PROD_PKGS)/$(PKG_NAME)'
	@scp $(DISTDIR)/* $(PROD_USER):$(PROD_PKGS)/$(PKG_NAME)/
	@echo ""
	@echo "Done."
	@echo ""

distribute_staging:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(STAGING_PKGS)"
	@test -d $(BUILDDIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(STAGING_PKGS)/$(PKG_NAME) || mkdir -p $(STAGING_PKGS)/$(PKG_NAME)'
	@scp $(DISTDIR)/* $(PROD_USER):$(STAGING_PKGS)/$(PKG_NAME)/
	@echo ""
	@echo "Done."
	@echo ""

distribute_staging_external:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(STAGING_EXT_PKGS)"
	@test -d $(BUILDDIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(STAGING_EXT_PKGS)/$(PKG_NAME) || mkdir -p $(STAGING_EXT_PKGS)/$(PKG_NAME)'
	@scp $(DISTDIR)/* $(PROD_USER):$(STAGING_EXT_PKGS)/$(PKG_NAME)/
	@echo ""
	@echo "Done."
	@echo ""

changelogs:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Generating changelog file"
	@echo ""
	@$(PYTHON) -c "from ciscodistutils.make_changelog import main; main('./docs/changelog/undistributed', './docs/changelog/undistributed.rst')"
	@echo "yang.connector changelog created..."
	@echo ""
	@echo "Done."
	@echo ""
