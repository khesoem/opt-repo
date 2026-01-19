docker run -it \
	--pull=always \
	-e SANDBOX_BASE_CONAINER_IMAGE={image} \
	-e SANDBOX_VOLUMES=/home/khesoem/postdoc-eth/projects/optimization-dataset/code/tmp/patched_repo:/workspace/project:rw \
	-e LOG_ALL_EVENTS=true \
	-e GITHUB_TOKEN="" \
	-v /run/docker.sock:/var/run/docker.sock \
	-v /home/khesoem/postdoc-eth/projects/optimization-dataset/code/tmp/openhands-files:/openhands-files \
	--add-host host.docker.internal:host-gateway \
	--name openhands-cli-$(date +%Y%m%d%H%M%S) \
	docker.openhands.dev/openhands/openhands:1.0.0 \
	python -m openhands.core.main -f /openhands-files/task-patch-generation.txt --config-file /openhands-files/config.toml
