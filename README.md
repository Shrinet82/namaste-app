# namaste-app

![tests](https://img.shields.io/badge/tests-unittest-brightgreen) ![python](https://img.shields.io/badge/python-3.12-blue) ![deps](https://img.shields.io/badge/dependencies-none-success)

A very small web app to try [Shipyard](https://github.com/Shrinet82/shipyard) with: three pods in a Kubernetes cluster, logs going to SigNoz, CI that produces an SBOM.

- `/` and `/hello?lang=ta&name=Anya` greet in Hindi, Tamil, Bengali, Marathi or English
- `/health` answers `ok`
- `/boom` logs an ERROR and answers 500, so there is something for SigNoz to alert on

No dependencies. `python -m unittest -v` runs the tests. `deploy/k8s.yaml` runs three replicas in the namespace `namaste`.
