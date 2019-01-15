mon-put-instance-data:
	docker build -t mon_put_instance_data -f Dockerfile.build .
	docker run --rm -v $(CURDIR):/mnt mon_put_instance_data cp dist/mon-put-instance-data /mnt/
