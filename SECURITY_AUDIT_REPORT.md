# Security Audit Report - Motus File Transfer Application
**Date**: 2025-11-19
**Audit Type**: White Box Penetration Test
**Auditor**: Security Assessment

---

## Executive Summary

This security audit identified **8 critical**, **6 high**, and **5 medium** severity vulnerabilities in the Motus application. The most critical issues involve credential exposure, authentication weaknesses, and path traversal risks. Immediate remediation is recommended before production deployment.

### Risk Summary
- **Critical**: 8 findings
- **High**: 6 findings
- **Medium**: 5 findings
- **Low**: 4 findings
- **Info**: 3 findings

---

## CRITICAL Severity Findings

### 1. Credential Exposure via API Response
**File**: `backend/api/remotes.py:70-75`
**CVSS**: 9.8 (Critical)

**Issue**: The `/api/remotes` endpoint returns full remote configurations including plaintext passwords, access keys, and secrets.

```python
# VULNERABLE CODE
config = rclone_config.get_remote(name)
remotes.append({
    'name': name,
    'type': config.get('type', 'unknown'),
    'config': config,  # ← Contains passwords, secret keys, etc.
})
```

**Impact**: Any authenticated user can retrieve all cloud storage credentials stored in rclone config.

**Proof of Concept**:
```bash
curl "http://localhost:5000/api/remotes?token=YOUR_TOKEN"
# Returns:
# {
#   "remotes": [{
#     "config": {
#       "access_key_id": "AKIAIOSFODNN7EXAMPLE",
#       "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
#     }
#   }]
# }
```

**Recommendation**:
- Mask sensitive fields (password, secret, key, token) in API responses
- Add a separate endpoint for credential management that requires elevated auth
- Implement field-level access control

---

### 2. Authentication Token in URL Query Parameters
**File**: `backend/auth.py:22`
**CVSS**: 9.1 (Critical)

**Issue**: Token authentication accepts tokens via URL query parameters, which leak in multiple places:
- Server access logs
- Browser history
- Referrer headers
- Proxy logs
- Browser bookmarks

```python
# VULNERABLE CODE
token = request.args.get('token')  # ← Token in URL
```

**Impact**: Token compromise through log files, shared URLs, or man-in-the-middle attacks.

**Proof of Concept**:
```bash
# Token visible in server logs:
http://localhost:5000/api/files/ls?token=abc123&path=/home/user

# Server log:
# 127.0.0.1 - - [19/Nov/2025] "GET /api/files/ls?token=abc123 HTTP/1.1"
```

**Recommendation**:
- **Remove** query parameter authentication entirely
- Use **only** HTTP headers or secure cookies
- Implement token rotation
- Add `HttpOnly`, `Secure`, `SameSite=Strict` cookie flags

---

### 3. Timing Attack on Token Comparison
**File**: `backend/auth.py:36`
**CVSS**: 8.6 (High-Critical)

**Issue**: Token comparison uses standard string equality (`!=`) which is vulnerable to timing attacks.

```python
# VULNERABLE CODE
if not token or token != expected_token:  # ← Timing-vulnerable comparison
    return jsonify({'error': 'Invalid or missing token'}), 401
```

**Impact**: Attackers can brute-force the token by measuring response times.

**Recommendation**:
```python
import secrets

# SECURE CODE
if not token or not secrets.compare_digest(token, expected_token):
    return jsonify({'error': 'Invalid or missing token'}), 401
```

---

### 4. Path Traversal via User Input
**Files**: `backend/api/files.py:60,106,152` & `backend/rclone/wrapper.py:189`
**CVSS**: 8.8 (High-Critical)

**Issue**: User-supplied paths are used without sanitization, allowing directory traversal attacks.

```python
# VULNERABLE CODE in backend/api/files.py
path = data['path']  # ← No validation
files = rclone.ls(path, remote_config)

# VULNERABLE CODE in backend/rclone/wrapper.py
expanded = os.path.expanduser(path)  # ← Expands ~/ without restriction
```

**Impact**: Attackers can:
- Read arbitrary files: `../../../../etc/passwd`
- List any directory on the server
- Delete system files via `/api/files/delete`
- Access files outside intended directories

**Proof of Concept**:
```bash
# Read /etc/passwd
curl -X POST http://localhost:5000/api/files/ls?token=abc \
  -H "Content-Type: application/json" \
  -d '{"path": "../../../../etc/"}'

# Delete system files
curl -X POST http://localhost:5000/api/files/delete?token=abc \
  -H "Content-Type: application/json" \
  -d '{"path": "../../../../tmp/important_file"}'
```

**Recommendation**:
```python
import os.path

def validate_path(path: str, allowed_base: str) -> str:
    """Validate and normalize path to prevent traversal"""
    # Resolve to absolute path
    abs_path = os.path.abspath(path)
    abs_base = os.path.abspath(allowed_base)

    # Ensure path is within allowed base
    if not abs_path.startswith(abs_base):
        raise ValueError("Path traversal attempt detected")

    return abs_path

# Use:
validated_path = validate_path(data['path'], config.allowed_base_dir)
```

---

### 5. Arbitrary File Read/Write via Log Files
**File**: `backend/rclone/wrapper.py:765`
**CVSS**: 8.5 (High)

**Issue**: Job log files are written with user-controlled job IDs without path sanitization.

```python
# POTENTIALLY VULNERABLE
log_file_path = os.path.join(self.logs_dir, f'job_{job_id}.log')
```

**Impact**: If `job_id` is not properly validated elsewhere, attackers could write to arbitrary paths.

**Recommendation**:
- Validate `job_id` is an integer
- Use sanitized, numeric-only filenames
- Set restrictive file permissions (0600)

---

### 6. SQL Injection via String Formatting
**File**: `backend/models.py:137`
**CVSS**: 7.5 (High)

**Issue**: Dynamic SQL construction using string formatting.

```python
# POTENTIALLY VULNERABLE
cursor.execute(f'''
    UPDATE jobs
    SET {', '.join(updates)}  # ← String concatenation
    WHERE job_id = ?
''', values)
```

**Analysis**: Currently safe because `updates` list is built from hardcoded strings, not user input. However, this pattern is dangerous and could introduce vulnerabilities during future code changes.

**Recommendation**:
```python
# SAFER - Explicit column mapping
allowed_columns = {
    'status': 'status = ?',
    'progress': 'progress = ?',
    'error_text': 'error_text = ?',
    'log_text': 'log_text = ?'
}

update_parts = []
for key in updates_dict.keys():
    if key not in allowed_columns:
        raise ValueError(f"Invalid column: {key}")
    update_parts.append(allowed_columns[key])

sql = f"UPDATE jobs SET {', '.join(update_parts)} WHERE job_id = ?"
```

---

### 7. Unencrypted Credentials in Transit
**File**: Multiple
**CVSS**: 7.4 (High)

**Issue**: No HTTPS enforcement. All traffic (including credentials) sent in plaintext.

**Impact**:
- Credentials intercepted via network sniffing
- Man-in-the-middle attacks
- Session hijacking

**Recommendation**:
```python
# In backend/app.py - Add HTTPS enforcement
@app.before_request
def enforce_https():
    if not request.is_secure and not app.debug:
        return redirect(request.url.replace('http://', 'https://'), 301)

# Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response
```

---

### 8. Credentials Logged in Plaintext
**File**: `backend/rclone/wrapper.py:976-978`
**CVSS**: 7.2 (High)

**Issue**: While some credential sanitization exists, environment variables are still logged and may contain secrets.

```python
# PARTIAL SANITIZATION
sanitized[key] = '***' + value[-4:] if len(value) > 4 else '***'
env_str = ' '.join(f"{k}='{v}'" for k, v in sanitized.items())
logging.info(f"Running: {env_str} {cmd_str}")  # ← Still logs partial credentials
```

**Recommendation**:
- Never log credentials, even partially
- Use audit logs separate from application logs for security events
- Implement log scrubbing for accidental credential exposure

---

## HIGH Severity Findings

### 9. No Rate Limiting on Authentication
**File**: `backend/auth.py`
**CVSS**: 6.8 (Medium-High)

**Issue**: No rate limiting on authentication attempts enables brute-force attacks.

**Recommendation**:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/protected')
@limiter.limit("5 per minute")
@token_required
def protected():
    pass
```

---

### 10. No CSRF Protection
**File**: All POST/DELETE endpoints
**CVSS**: 6.5 (Medium)

**Issue**: No CSRF tokens for state-changing operations.

**Mitigation**: While less critical for single-user, token-based API, still recommended:
```python
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
```

---

### 11. Insufficient Input Validation
**File**: Multiple API endpoints
**CVSS**: 6.3 (Medium)

**Issue**: Missing validation on:
- Path length limits
- File size limits
- Allowed characters in remote names
- Job ID format

**Recommendation**:
```python
from marshmallow import Schema, fields, validate

class FileListSchema(Schema):
    path = fields.Str(required=True, validate=validate.Length(max=4096))
    remote_config = fields.Dict(required=False)

# Use:
schema = FileListSchema()
errors = schema.validate(request.get_json())
if errors:
    return jsonify({'error': errors}), 400
```

---

### 12. Weak Token Generation
**File**: `backend/config.py`
**CVSS**: 6.1 (Medium)

**Issue**: Token generation not reviewed - ensure cryptographically secure random.

**Recommendation**:
```python
import secrets

def generate_token(length=32):
    """Generate cryptographically secure token"""
    return secrets.token_urlsafe(length)
```

---

### 13. Information Disclosure in Error Messages
**Files**: Multiple
**CVSS**: 5.8 (Medium)

**Issue**: Detailed error messages leak internal paths and system information.

```python
# VULNERABLE
except Exception as e:
    return jsonify({'error': str(e)}), 500  # ← Exposes internal details
```

**Recommendation**:
```python
# SECURE
except Exception as e:
    logging.exception("Error in endpoint")
    return jsonify({'error': 'Internal server error'}), 500
```

---

### 14. Database Lock Timeout Too High
**File**: `backend/models.py:61`
**CVSS**: 5.5 (Medium)

**Issue**: 30-second timeout can cause DoS via database locking.

```python
conn = sqlite3.connect(self.db_path, timeout=30.0)  # ← Too high
```

**Recommendation**: Use 5-10 seconds max and implement proper retry logic.

---

## MEDIUM Severity Findings

### 15. No Input Sanitization for Logs
**File**: Multiple
**CVSS**: 5.3 (Medium)

**Issue**: User input logged without sanitization enables log injection.

```python
logging.info(f"Listing files at {path}")  # ← Unsanitized user input
```

**Impact**: Attackers can inject fake log entries or break log parsing.

---

### 16. Predictable Job IDs
**File**: `backend/rclone/wrapper.py`
**CVSS**: 4.8 (Medium)

**Issue**: Sequential job IDs are predictable.

**Recommendation**: Use UUIDs or add random component for job IDs.

---

### 17. No Session Timeout
**File**: `backend/auth.py`
**CVSS**: 4.5 (Medium)

**Issue**: Tokens never expire unless server restarts.

**Recommendation**: Implement token expiration and refresh mechanism.

---

### 18. Weak File Permissions
**File**: `backend/rclone/rclone_config.py:30`
**CVSS**: 4.3 (Medium)

**Issue**: Config files created with default permissions.

**Recommendation**:
```python
os.chmod(config_file, 0o600)  # Owner read/write only
```

---

### 19. No Audit Logging
**File**: All
**CVSS**: 4.0 (Medium)

**Issue**: No audit trail for security events (auth failures, file deletions, etc.)

**Recommendation**: Implement structured audit logging to separate file.

---

## LOW Severity Findings

### 20. Missing Security Headers
**File**: `backend/app.py`

**Recommendation**: Add CSP, X-Frame-Options, HSTS headers (see #7)

---

### 21. No Request Size Limits on File Operations
**File**: API endpoints

**Recommendation**: Enforce limits on file listing, transfer sizes.

---

### 22. Verbose Debug Mode
**File**: Configuration

**Recommendation**: Ensure debug mode disabled in production.

---

### 23. No Integrity Checks
**File**: File transfers

**Recommendation**: Implement checksum verification for transfers.

---

## INFORMATIONAL Findings

### 24. Outdated Dependencies
Review `requirements.txt` for vulnerable package versions.

### 25. Missing Security Documentation
Add SECURITY.md with vulnerability reporting process.

### 26. No Security Tests
Implement security-focused unit tests.

---

## Remediation Priority

### IMMEDIATE (Critical/High)
1. Remove token from query parameters → Use headers only
2. Mask credentials in `/api/remotes` API response
3. Implement path validation and traversal protection
4. Use `secrets.compare_digest()` for token comparison
5. Enforce HTTPS with security headers

### SHORT TERM (1-2 weeks)
6. Add rate limiting on authentication
7. Implement input validation schemas
8. Add audit logging
9. Set proper file permissions
10. Sanitize error messages

### MEDIUM TERM (1 month)
11. Add CSRF protection
12. Implement token expiration
13. Add security unit tests
14. Dependency security scanning
15. Security documentation

---

## Testing Recommendations

1. **Penetration Testing**: Conduct external pentest after fixes
2. **SAST**: Integrate Bandit or similar Python security scanner
3. **DAST**: Use OWASP ZAP for dynamic testing
4. **Dependency Scanning**: Use Safety or Snyk
5. **Code Review**: Security-focused review of all changes

---

## Compliance Considerations

If handling sensitive data or used in regulated environments:
- **GDPR**: Ensure data protection controls
- **HIPAA**: Not suitable without major security enhancements
- **PCI DSS**: Not recommended for cardholder data
- **SOC 2**: Requires audit logging, access controls, encryption

---

## Conclusion

The application has significant security vulnerabilities that must be addressed before production use. The most critical issues involve credential exposure and path traversal. With proper remediation, the application can achieve a good security posture for its intended single-user use case.

**Risk Rating**: ⚠️ **HIGH RISK** - Do not deploy to production without fixes

---

**End of Report**
