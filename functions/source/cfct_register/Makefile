PROJECT = NewRelicCfCTRegister
DIR_NAME = cfct_register
FUNCTION = $(PROJECT)
DIST_DIR ?= "$(BASE)"/functions/packages/$(DIR_NAME)
$(shell mkdir -p $(DIST_DIR))

all: build

.PHONY: clean build

clean:
	rm -rf build

build: clean
	mkdir -p build
	rm -f $(DIST_DIR)/$(FUNCTION).zip
	zip -r $(DIST_DIR)/$(FUNCTION).zip . -x "*.DS_Store*" "*.git*" "build*" "Makefile" "requirements.txt"
	python3 -m venv build/$(FUNCTION)
	. build/$(FUNCTION)/bin/activate; \
	pip3 install  -r requirements.txt -t build/lib/; \
	cd build/lib/; zip -g -r $(DIST_DIR)/$(FUNCTION).zip . -x "*__pycache__*"
	rm -rf build
