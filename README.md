# IoMBian Installed Services Handler

This services takes care of starting and stopping the compose of the services whenever a services is added or removed to the "iombian-services" folder.
It also restarts the services when a change occurs in them.

This handler allows manual creation of services in the "iombian-services" folder, but the use of "IoMBian Installed Services Downloader" is recommended.

## Docker
To build the docker image, from the cloned repository, execute the docker build command in the same level as the Dockerfile:

```
docker build -t ${IMAGE_NAME}:${IMAGE_VERSION} .
```

For example `docker build -t iombian-installed-services-handler:latest .`

After building the image, execute it with docker run:

```
docker run --name ${CONTAINER_NAME} --rm -d -v /opt/iombian-services:/opt/iombian-services -v /var/run/docker.sock:/var/run/docker.sock -v /usr/bin/docker:/usr/bin/docker -v /usr/libexec/docker/cli-plugins/docker-compose:/usr/libexec/docker/cli-plugins/docker-compose -e BASE_PATH=/opt/iombian-services iombian-installed-services-handler:latest
```

- **--name** is used to define the name of the created container.
- **--rm** can be used to delete the container when it stops. This parameter is optional.
- **-d** is used to run the container detached. This way the container will run in the background. This parameter is optional.
- **-v** is used to pass volumes to the container.
In this case, the volumes map some files that are used to be able to use docker from inside the docker container.
    - **/opt/iombian-services** is the folder where the installed services are stored.
    - **/var/run/docker.sock** is the docker socket that communicates the docker client and the docker daemon.
    - **/usr/bin/docker** is the docker binary to use the host machines docker from the container.
    - **/usr/libexec/docker/cli-plugins/docker-compose** is the docker compose plugin binary.
- **-e** can be used to define the environment variables:
    - BASE_PATH: the path where the installed services are stored.
    Default value is "/opt/iombian-services".
    - WAIT_SECONDS: the time waited between changes to a service before restarting the service compose.
    It waits this time so multiple files can be edited at the same time without the service staring and stopping multiple times.
    Default value is 1.
    - LOG_LEVEL: define the log level for the python logger.
    This can be DEBUG, INFO, WARN or ERROR.
    Default value is INFO.

Otherwise, a `docker-compose.yml` file can also be used to launch the container:

```
version: 3

services:
  iombian-installed-services-handler:
    image: iombian-installed-services-handler:latest
    container_name: iombian-installed-services-handler
    restart: unless_stopped
    volumes:
      - /opt/iombian-services:/opt/iombian-services
      - /var/run/docker.sock:/var/run/docker.sock
      - /usr/bin/docker:/usr/bin/docker
      - /usr/libexec/docker/cli-plugins/docker-compose:/usr/libexec/docker/cli-plugins/docker-compose
    environment:
      BASE_PATH: "/opt/iombian-services"
      WAIT_SECONDS: 1
      LOG_LEVEL: "INFO"
```

```
docker compose up -d
```

## Author
(c) 2024 IoMBian team ([Aitor Iturrioz Rodríguez](https://github.com/bodiroga), [Aitor Castaño Mesa](https://github.com/aitorcas23)).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
