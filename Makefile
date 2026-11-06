# Воспроизводимый запуск. Параметры: make experiment SEEDS="0 1 2" TEMP=0.2
PY      ?= python
PARTS   ?= parts
PROCESS ?= process.json
RUNS    ?= runs
SEEDS   ?= 0 1 2
TEMP    ?= 0.2

install:            ## зависимости (CPU-часть); на GPU-машине дополнительно: pip install vllm
	$(PY) -m pip install -r requirements.txt

baseline:           ## стоимость и самопроверка исходных деталей (без LLM)
	$(PY) -m dfm.evaluate --parts $(PARTS) --process $(PROCESS) --out baseline.csv

debug-access:       ## make debug-access PART=parts/<id>
	$(PY) -m dfm.debug_access $(PART)

experiment:         ## все модели из models.json: loop + oneshot, по seed'ам (нужна GPU и vllm)
	$(PY) -m dfm.run_models --models models.json --parts $(PARTS) --process $(PROCESS) \
	      --runs $(RUNS) --seeds $(SEEDS) --temperature $(TEMP)

dry-run:
	$(PY) -m dfm.run_models --dry-run --seeds $(SEEDS)

compare:
	$(PY) -m dfm.compare --runs $(RUNS) --out results.csv

sft-data:           ## траектории -> data/{trajectories,sft,dpo}.jsonl
	$(PY) -m dfm.export_sft --runs $(RUNS) --out data

freeze:             ## зафиксировать окружение
	mkdir -p $(RUNS) && $(PY) -m pip freeze > $(RUNS)/env.txt && nvidia-smi >> $(RUNS)/env.txt || true

.PHONY: install baseline debug-access experiment dry-run compare sft-data freeze
