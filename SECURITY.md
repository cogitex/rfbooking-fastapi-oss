# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### How to Report

Email: **oleg.tokmakov@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Initial response**: tbd.
- **Status update**: tbd.
- **Fix timeline**: tbd.

### What to Expect

1. Acknowledgment of your report
2. Assessment of the vulnerability
3. Development of a fix
4. Security advisory and release
5. Credit in the advisory (if desired)

## Security Best Practices

When deploying RFBooking FastAPI OSS:

### Configuration

- [ ] Change default `secret_key` in config.yaml
- [ ] Use strong, unique secret key (32+ characters)
- [ ] Set `debug: false` in production
- [ ] Configure proper `base_url` for your domain

### Network

- [ ] Use HTTPS with valid SSL certificate
- [ ] Place behind reverse proxy (Nginx/Caddy)
- [ ] Firewall: only expose ports 80/443
- [ ] Don't expose port 8000 directly to internet

### Access

- [ ] Use strong admin email
- [ ] Review user access regularly
- [ ] Disable inactive users promptly

### Data

- [ ] Regular backups of database
- [ ] Secure backup storage
- [ ] Test restore procedures

### Updates

- [ ] Monitor for security updates
- [ ] Apply updates promptly
- [ ] Subscribe to release notifications

## Known Security Features

- **Passwordless authentication**: No passwords stored
- **HTTP-only cookies**: Session tokens not accessible to JavaScript
- **CSRF protection**: Double submit cookie pattern
- **Input sanitization**: HTML escaping, length limits
- **Rate limiting**: Prevents brute force attacks
- **Role-based access control**: Admin/Manager/User hierarchy

## Scope

### In Scope

- Authentication bypass
- SQL injection
- Cross-site scripting (XSS)
- Cross-site request forgery (CSRF)
- Remote code execution
- Privilege escalation
- Data exposure

### Out of Scope

- Denial of service (DoS)
- Social engineering
- Physical security
- Issues in dependencies (report upstream)
- Self-hosted misconfigurations

---

Copyright (C) 2025 Oleg Tokmakov
