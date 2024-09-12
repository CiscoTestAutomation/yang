# Variables
ROOTDIR       = $(shell pwd)
ALL_CMDS      = package test distribute distribute_staging distribute_staging_external clean develop undevelop docs changelogs

.PHONY: clean package distribute distribute_staging distribute_staging_external\
        develop undevelop populate_dist_dir help docs distribute_docs test

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo ""
	@echo "package                      : Build the packages"
	@echo "test                         : Test the packages"
	@echo "distribute                   : Distribute the packages to PyPi server"
	@echo "distribute_staging           : Distribute the packages to staging area"
	@echo "distribute_staging_external  : Distribute the packages to external staging area"
	@echo "clean                        : Remove build artifacts"
	@echo "develop                      : Build and install development packages"
	@echo "undevelop                    : Uninstall development packages"
	@echo "docs                         : Build Sphinx documentation for these packages"

$(ALL_CMDS):
	cd $(ROOTDIR)/connector; make $@
	cd $(ROOTDIR)/ncdiff; make $@
