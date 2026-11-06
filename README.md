# dfm-agent (минимальная версия LLM-Aided DFM)

Структура:
```
dfm/worker.py    запуск part.py в отдельном процессе -> STEP
dfm/sandbox.py   run_code(code) -> RunResult(ok, shape, error)
dfm/geom.py      отверстия, острые внутренние углы, сетка, лучи (доступность, стенки)
dfm/checks.py    check_spec(shape, ref, spec)   <- Verifier (ТЗ)
dfm/cost.py      compute_cost(shape, process)   <- модель стоимости + список проблем
dfm/evaluate.py  базовый прогон по датасету (CPU, без LLM)
dfm/llm.py       клиент OpenAI-совместимого сервера (vLLM/Ollama)
dfm/agents.py    Reviewer, Modifier, Verifier
dfm/loop.py      агентный цикл по всем деталям
parts/<id>/part.py, spec.json, *.step    <- ваш датасет
process.json     условия производства
examples/        три тестовые детали (a: острые углы, b: исправленная a, c: скругления)
```

## 1. Локально (CPU): baseline по датасету
```
pip install -r requirements.txt
python -m dfm.evaluate --parts parts --process process.json --out baseline.csv
```
Смотрите baseline.csv и parts/<id>/cost_report.json (там features и issues).

## 2. Kaggle: поднять модель
```
!pip install -q vllm requests cadquery
import subprocess, time, requests
srv = subprocess.Popen(["vllm","serve","Qwen/Qwen2.5-Coder-7B-Instruct-AWQ",
    "--quantization","awq","--dtype","half","--max-model-len","8192",
    "--gpu-memory-utilization","0.90","--port","8000"],
    stdout=open("vllm.log","w"), stderr=subprocess.STDOUT)
for _ in range(120):
    try: requests.get("http://localhost:8000/v1/models", timeout=2); break
    except Exception: time.sleep(5)
```
## 3. Kaggle: запуск цикла
```
%cd /kaggle/working/dfm-agent
!python -m dfm.loop --parts parts --process process.json --out runs/qwen7b --max-steps 5 --retries 4
```
Результаты: runs/<модель>/<id>/{trajectory.jsonl, final.py, summary.json}.
Прогон возобновляемый: детали с summary.json пропускаются.
Другая модель: переменные окружения LLM_BASE_URL, LLM_MODEL.

---
## Эксперимент: loop vs one-shot, несколько моделей
```
make baseline                       # CPU: стоимость исходных деталей
make debug-access PART=parts/<id>   # какие грани считаются недоступными (штраф выключен по умолчанию)
make dry-run                        # посмотреть, какие команды будут выполнены
make experiment SEEDS="0 1 2"       # GPU: для каждой модели из models.json -> loop + oneshot
make compare                        # results.csv + results.summary.csv
make sft-data                       # data/trajectories.jsonl, sft.jsonl, dpo.jsonl
make freeze                         # runs/env.txt (pip freeze + nvidia-smi)
```
Структура результатов: `runs/<model>/seed<k>/<loop|oneshot>/<part>/{summary.json, final.py, trajectory.jsonl}`;
в каждой папке метода лежит `config.json` (модель, temperature, seed, process).
Одна модель: `python -m dfm.run_models --only qwen25coder7b --seeds 0`.
