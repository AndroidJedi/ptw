# Host bootstrap record

Bootstrap date: 2026-08-11 UTC.

The host began as Ubuntu 24.04.4 LTS with 1 vCPU, 961 MiB RAM, no swap, and a
24 GiB root disk. Git, curl, Python, and Codex CLI were present. Docker Engine
and the Docker Compose plugin were installed from Ubuntu's Noble repositories.
Docker was enabled through systemd.

Before deployment, TCP port 22 (SSH) was the only public listening port. UFW
was inactive. No firewall, SSH, DNS, DigitalOcean, user-account, or disk-layout
changes were made.

Caddy publishes only to `127.0.0.1:8080` by default. Deliberately exposing it
requires an explicit bind-address change plus a reviewed authentication and
firewall design.

