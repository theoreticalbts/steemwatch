#!/bin/bash
export IMAGE_NAME="theoreticalbts/steemwatch:${GIT_BRANCH#*/}"
sudo docker build -t=$IMAGE_NAME .
