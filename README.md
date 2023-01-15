# python-docker

### Install

`pip install -r requirements.txt`

### Run container with AWS logging

`python main.py --docker-image python --bash-command $'pip install -U pip && python -uc \"import time\ncounter = 0\nwhile True:\n\tprint(counter)\n\tcounter = counter + 1\n\ttime.sleep(0.1)\"' --aws-region us-west-1 --aws-access-key-id *** --aws-secret-access-key *** --aws-cloudwatch-group test-task-group-1 --aws-cloudwatch-stream test-task-stream-1`
