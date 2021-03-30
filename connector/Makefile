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
PKG_PATH      = yang/connector
BUILDDIR      = $(shell pwd)/__build__
PROD_USER     = pyadm@pyats-ci
PROD_PKGS     = /auto/pyats/packages
STAGING_PKGS  = /auto/pyats/staging/packages
PYTHON        = pythons
TESTCMD       = cd tests; runAll
DISTDIR       = $(BUILDDIR)/dist

.PHONY: clean package distribute distribute_staging develop undevelop \
	    populate_dist_dir help docs distribute_docs test

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo ""
	@echo "package              : Build the package"
	@echo "test                 : Test the package"
	@echo "distribute           : Distribute the package to PyPi server"
	@echo "distribute_staging   : Distribute the package to staging area"
	@echo "clean                : Remove build artifacts"
	@echo "develop              : Build and install development package"
	@echo "undevelop            : Uninstall development package"
	@echo "html                 : Build Sphinx documentation for this package"

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

    # TBD - remove
	#@./setup.py test
	#@mkdir -p $(DISTDIR)

    # NOTE : Only specify --universal if the package works for both py2 and py3
    # https://packaging.python.org/en/latest/distributing.html#universal-wheels
	@./setup.py bdist_wheel --dist-dir=$(DISTDIR)
	@./setup.py sdist --dist-dir=$(DISTDIR)

	@echo "Completed building: $@"
	@echo ""
	@echo "Done."
	@echo ""

develop:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building and installing $(PKG_NAME) development distributable: $@"
	@echo ""

	@./setup.py develop -q

	@echo "Completed building and installing: $@"
	@echo ""
	@echo "Done."
	@echo ""

undevelop:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Uninstalling $(PKG_NAME) development distributable: $@"
	@echo ""

	@./setup.py develop -q --uninstall

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
	@./setup.py clean
	@echo ""
	@echo "Done."
	@echo ""

distribute:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(PROD_PKGS)"
	@test -d $(BUILDDIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(PROD_PKGS)/$(PKG_PATH) || mkdir $(PROD_PKGS)/$(PKG_PATH)'
	@scp $(DISTDIR)/* $(PROD_USER):$(PROD_PKGS)/$(PKG_PATH)/
	@echo ""
	@echo "Done."
	@echo ""

distribute_staging:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(STAGING_PKGS)"
	@test -d $(BUILDDIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(STAGING_PKGS)/$(PKG_PATH) || mkdir $(STAGING_PKGS)/$(PKG_PATH)'
	@scp $(DISTDIR)/* $(PROD_USER):$(STAGING_PKGS)/$(PKG_PATH)/
	@echo ""
	@echo "Done."
	@echo ""
