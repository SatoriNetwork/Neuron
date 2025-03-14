to reclaim space
kill all docker containers
remove containers and images you don't need

```
docker stop <container>
docker rm <container>
docker rmi
docker buildx prune --all
docker builder prune --all
docker image prune -f
docker system prune -f
docker volume prune -f
docker volume ls
docker volume rm <name>
docker system df

```

sometimes windows docker system will boat and take up more memory over time. Here's how you can reclaim that memory:

Run these commands in an administrator powershell
```
# backup the images you want to keep
docker save -o multiple_images.tar satorinet/satorineuron:latest satorinet/satoricentral:base

# here's how you can load those images if you need to
# docker load -i multiple_images.tar

# stop wsl
wsl --shutdown

# Verify everything is stopped by:
wsl --list --verbose

# Then start diskpart:
diskpart

# and inside diskpart type:
DISKPART> select vdisk file="C:\Users\<USERNAME>\AppData\Local\Docker\wsl\data\ext4.vhdx"

# Then to shrink
DISKPART> compact vdisk
DISKPART> exit
```
