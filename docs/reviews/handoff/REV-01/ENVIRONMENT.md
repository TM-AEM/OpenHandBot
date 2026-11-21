# REV-01 Packaging Environment

## Packaging environment

| Item | Value |
|---|---|
| Source workspace | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD at packaging | `7cb9d7a0b37feac986e21622bfadd69a4baec978` |
| Base tree | `2ccdb866dce467dad55d3d83f0f757324d00409b` |
| Python | 3.13.15 |
| pytest | unavailable (`No module named pytest`) |
| Node.js | v24.22.2 |
| Git | 2.47.3 |
| OS/kernel | Linux 6.8.0-1055-gke x86_64 |

## Historical implementation environment (attributed)

The implementation report states:

- Python 3.13.15
- pytest 9.0.3

Those historical test results are included only in `TEST-EVIDENCE.md` as attributed claims. The current
packaging environment cannot reproduce them without installing the declared development dependencies.

## Reviewer setup

In the independent reviewer workspace:

```sh
pip install -r requirements-dev.txt
python3 -m pytest --version
node --version
```

The reviewer should record its own exact Python, pytest, Node.js, and dependency versions in its separate
review report.
