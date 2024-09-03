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
wsl.exe --list --verbose

# Then start diskpart:
diskpart

# and inside diskpart type:
DISKPART> select vdisk file="<path to vhdx file>"

# Then to shrink
DISKPART> compact vdisk
DISKPART> exit
```
