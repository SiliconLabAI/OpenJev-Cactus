# - Install needle
```bash

git clone https://github.com/cactus-compute/needle.git
%cd needle
pip install -e ".[train]"
# build binary
needle build --platform linux-x86_64

# if need not install correctly with git repo, reinstall
pip uninstall -y needle cactus-needle
pip install -U cactus-needle

import needle
print(needle.__file__)
print(dir(needle))

```

```bash
# run needle server localhost:8080
# path/to/needle
# /path/to/needle/linux-x86_64/needle --model /path/to/needle/linux-x86_64/needle3.cact --tools /path/to/needle/tools.json --serve

```

# issues
```bash

# huggingface_hub.errors.RemoteEntryNotFoundError: 404 Client Error. (Request ID: Root=1-6ab40267-5d82dc4809c71a0d7a459b2a;4f4f5c38-846d-41f6-8065-5f433945e5e4)

# Entry Not Found for url: https://huggingface.co/Cactus-Compute/needle3/resolve/main/python/cactus_needle-3.0.2-py3-none-manylinux2014_x86_64.whl.

# 1. Download the existing wheel
mkdir -p /tmp/needle-engine && cd /tmp/needle-engine
wget https://huggingface.co/Cactus-Compute/needle3/resolve/main/python/cactus_needle-3.0.1-py3-none-manylinux2014_x86_64.whl

# 2. Extract the shared library
unzip -o cactus_needle-3.0.1-py3-none-manylinux2014_x86_64.whl
# Look for something like: needle/libneedle3.so  (or libneedle.so)
find . -name "*.so" -o -name "libneedle*"

# 3. Point the package at it
export NEEDLE3_LIB_PATH=/tmp/needle-engine/needle/libneedle3.so   # use the real path from find

# 4. Also download weights if needed
needle download needle3 --out ~/.cache/cactus-needle/v3/
```

```bash
# run local tests
python tests/test_needle.py
python tests/test_needle2.py

```

```bash
# 5. Restart your FastAPI server in the same shell
cd /srv/www/needle-fastapi-app
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

```

