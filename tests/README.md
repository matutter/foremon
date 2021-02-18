# foremon testing

Testing is performed by either _[PyTest][pytest]_ via _[tox][tox]_ or
_[Expect][expect]_ and may be done manually or automatically with CI from
[Github Actions][actions].

[pytest]: https://docs.pytest.org/en/stable/
[tox]: https://tox.readthedocs.io/en/latest/
[expect]: https://linux.die.net/man/1/expect
[actions]: https://github.com/features/actions

# Manual testing

These commands are used for testing manually.

### PyTest

Testing fast with _xdist_.

```bash
# with coverage ~6s
py.test -n auto --cov=foremon --cov-report=html

# without coverage ~4s
py.test -n auto
```

### Expect

Testing with _expect_ requires `foremon` to be installed. Alternatively the
`tests/expect/docker.sh` script uses docker to perform these tests. Docker
provides a way to run expect in a _clean_ environment similar to the CI
pipeline.

```bash
# Build foremon
python -m build
# Install foremon
pip install dist/foremon*.tar.gz
# Run expect manually
expect tests/expect/basic.exp
```

Using docker.

```bash
# Build foremon
python -m build
# Run tests in python:3.8
./scripts/expect/docker.sh
./scripts/expect/docker.sh 3.6
./scripts/expect/docker.sh 3.7
./scripts/expect/docker.sh 3.9
```
