# Reproducible pipeline for the AlgoMusic reverse-engineering.

GHIDRA ?= /home/mark/buildhome/ghidra/ghidra_12.0.4_PUBLIC
HUNKTOOL ?= $(HOME)/.local/bin/hunktool
BIN := orig/AlgoMusic/AlgoMusic.000

.PHONY: all download extract db ghidra run verify clean

all: download extract db

download:
	curl -sL -A "Mozilla/5.0" -o AlgoMusic2_4u.lha https://aminet.net/mus/misc/AlgoMusic2_4u.lha
	curl -sL -A "Mozilla/5.0" -o AlgoMusic2_4.lha  https://aminet.net/mus/misc/AlgoMusic2_4.lha
	mkdir -p orig full
	cd orig && lha -x ../AlgoMusic2_4u.lha >/dev/null 2>&1 || true
	cd full && lha -x ../AlgoMusic2_4.lha  >/dev/null 2>&1 || true

extract:
	python3 tools/extract_hunk.py $(BIN) work/algomusic 0x100000

db: extract
	python3 tools/extract_db.py
	python3 tools/extract_comments.py

ghidra:
	mkdir -p work/ghidra_proj
	$(GHIDRA)/support/analyzeHeadless work/ghidra_proj AlgoMusic \
	  -import work/algomusic.bin -processor "68000:BE:32:default" \
	  -loader BinaryLoader -loader-baseAddr 0x00100000 \
	  -scriptPath tools -preScript ghidra_prep.py
	$(GHIDRA)/support/analyzeHeadless work/ghidra_proj AlgoMusic \
	  -process -noanalysis -scriptPath tools -postScript ghidra_export.py

run:
	python3 -m algomusic -s '$$4002' -o algomusic.wav

verify:
	python3 tools/verify_groundtruth.py
	python3 tools/verify_tables.py
	python3 tools/verify_comments.py

clean:
	rm -rf work
