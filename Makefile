PY ?= python3
export PYTHONPATH := src

.PHONY: all download extract build analyze test clean

all: download extract build analyze

download:
	$(PY) -m gender_gap download

extract:
	$(PY) -m gender_gap extract

build:
	$(PY) -m gender_gap build

analyze:
	$(PY) -m gender_gap analyze

test:
	$(PY) -m pytest -q

clean:
	rm -rf data/processed/*.parquet data/processed/*.csv reports/*.md reports/figures/*.png
