# CTFd-Whale

## [中文README](README.zh-cn.md)

A plugin that empowers CTFd to bring up separate environments for each user

## Features

- Deploys containers with `frp` and `docker swarm`
- Supports subdomain access by utilizing `frp`
- Contestants can start/renew/destroy their environments with a single click
- flags and subdomains are generated automatically with configurable rules
- Administrators can get a full list of running containers, with full control over them.

## Installation & Usage

refer to [INSTALL.md](INSTALL.md)

## Demo

[BUUCTF](https://buuoj.cn)

## Third-party Introductions (zh-CN)

- [CTFd-Whale 推荐部署实践](https://www.zhaoj.in/read-6333.html)
- [手把手教你如何建立一个支持ctf动态独立靶机的靶场（ctfd+ctfd-whale)](https://blog.csdn.net/fjh1997/article/details/100850756)

## Screenshots

![](https://www.zhaoj.in/wp-content/uploads/2019/08/1565947849bb2f3ed7912fb85afbbf3e6135cb89ca.png)

![](https://www.zhaoj.in/wp-content/uploads/2019/08/15659478989e90e7a3437b1bdd5b9e617d7071a79f.png)

![](https://www.zhaoj.in/wp-content/uploads/2019/08/15659479342f5f6d33e2eeaedb313facd77b2bbccb.png)

![](https://www.zhaoj.in/wp-content/uploads/2019/08/1565923903609e6c236759a5663be8e0fb57904482.png)

## Twin Project

- [CTFd-Owl](https://github.com/D0g3-Lab/H1ve/tree/master/CTFd/plugins/ctfd-owl) (支持部署compose)
