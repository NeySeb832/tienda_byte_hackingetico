# ZAP Scanning Report

ZAP by [Checkmarx](https://checkmarx.com/).


## Summary of Alerts

| Risk Level | Number of Alerts |
| --- | --- |
| High | 0 |
| Medium | 2 |
| Low | 7 |
| Informational | 5 |




## Insights

| Level | Reason | Site | Description | Statistic |
| --- | --- | --- | --- | --- |
| Info | Informational |  | Percentage of network failures | 1 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of responses with status code 2xx | 54 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of responses with status code 3xx | 35 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of responses with status code 4xx | 10 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type application/octet-stream | 14 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type image/svg+xml | 1 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type text/css | 1 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type text/html | 82 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with content type text/javascript | 1 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method GET | 75 % |
| Info | Informational | http://host.docker.internal:8001 | Percentage of endpoints with method POST | 25 % |
| Info | Informational | http://host.docker.internal:8001 | Count of total endpoints | 276    |
| Info | Informational | http://host.docker.internal:8001 | Percentage of slow responses | 79 % |







## Alerts

| Name | Risk Level | Number of Instances |
| --- | --- | --- |
| Content Security Policy (CSP) Header Not Set | Medium | Systemic |
| Sub Resource Integrity Attribute Missing | Medium | Systemic |
| Cross-Domain JavaScript Source File Inclusion | Low | Systemic |
| Cross-Origin-Embedder-Policy Header Missing or Invalid | Low | 3 |
| Cross-Origin-Resource-Policy Header Missing or Invalid | Low | Systemic |
| Dangerous JS Functions | Low | 1 |
| Permissions Policy Header Not Set | Low | 5 |
| Server Leaks Version Information via "Server" HTTP Response Header Field | Low | Systemic |
| X-Content-Type-Options Header Missing | Low | Systemic |
| Authentication Request Identified | Informational | 2 |
| Information Disclosure - Suspicious Comments | Informational | 1 |
| Session Management Response Identified | Informational | 11 |
| Storable and Cacheable Content | Informational | Systemic |
| User Controllable HTML Element Attribute (Potential XSS) | Informational | 9 |




## Alert Detail



### [ Content Security Policy (CSP) Header Not Set ](https://www.zaproxy.org/docs/alerts/10038/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks, including Cross Site Scripting (XSS) and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://host.docker.internal:8001/devolucion/
  * Node Name: `http://host.docker.internal:8001/devolucion/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/factura/
  * Node Name: `http://host.docker.internal:8001/factura/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/responder/
  * Node Name: `http://host.docker.internal:8001/responder/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/sitemap.xml
  * Node Name: `http://host.docker.internal:8001/sitemap.xml`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is configured to set the Content-Security-Policy header.

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP ](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP)
* [ https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://w3c.github.io/webappsec-csp/ ](https://w3c.github.io/webappsec-csp/)
* [ https://web.dev/articles/csp ](https://web.dev/articles/csp)
* [ https://caniuse.com/#feat=contentsecuritypolicy ](https://caniuse.com/#feat=contentsecuritypolicy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ Sub Resource Integrity Attribute Missing ](https://www.zaproxy.org/docs/alerts/90003/)



##### Medium (High)

### Description

The integrity attribute is missing on a script or link tag served by an external server. The integrity tag prevents an attacker who have gained access to this server from injecting a malicious content.

* URL: http://host.docker.internal:8001/cuenta/password/reset/
  * Node Name: `http://host.docker.internal:8001/cuenta/password/reset/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script nonce="tk0hhjHcDbza11DyHzgG1A==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/signup/
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script nonce="cO0AKiTyNSTUg1soAcWaEQ==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/signup/%3Fnext=%252Fcuenta%252Fretomas%252F
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/ (next)`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script nonce="MdCb8X9iI5RUIzKWLp4dJg==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/password/reset/
  * Node Name: `http://host.docker.internal:8001/cuenta/password/reset/ ()(csrfmiddlewaretoken,email,website)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script nonce="g+H0Oh+daEaQv0Uj+Uz3BA==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/signup/
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/ ()(accept_privacy,csrfmiddlewaretoken,email,first_name,last_name,next,password1,password2,website)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<script nonce="HTK43G0VuNYDRy0QFqo8gw==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``

Instances: Systemic


### Solution

Provide a valid integrity attribute to the tag.

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity ](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Subresource_Integrity)


#### CWE Id: [ 345 ](https://cwe.mitre.org/data/definitions/345.html)


#### WASC Id: 15

#### Source ID: 3

### [ Cross-Domain JavaScript Source File Inclusion ](https://www.zaproxy.org/docs/alerts/10017/)



##### Low (Medium)

### Description

The page includes one or more script files from a third-party domain.

* URL: http://host.docker.internal:8001/cuenta/password/reset/
  * Node Name: `http://host.docker.internal:8001/cuenta/password/reset/`
  * Method: `GET`
  * Parameter: `https://challenges.cloudflare.com/turnstile/v0/api.js`
  * Attack: ``
  * Evidence: `<script nonce="tk0hhjHcDbza11DyHzgG1A==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/signup/
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/`
  * Method: `GET`
  * Parameter: `https://challenges.cloudflare.com/turnstile/v0/api.js`
  * Attack: ``
  * Evidence: `<script nonce="cO0AKiTyNSTUg1soAcWaEQ==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/signup/%3Fnext=%252Fcuenta%252Fretomas%252F
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/ (next)`
  * Method: `GET`
  * Parameter: `https://challenges.cloudflare.com/turnstile/v0/api.js`
  * Attack: ``
  * Evidence: `<script nonce="MdCb8X9iI5RUIzKWLp4dJg==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/password/reset/
  * Node Name: `http://host.docker.internal:8001/cuenta/password/reset/ ()(csrfmiddlewaretoken,email,website)`
  * Method: `POST`
  * Parameter: `https://challenges.cloudflare.com/turnstile/v0/api.js`
  * Attack: ``
  * Evidence: `<script nonce="g+H0Oh+daEaQv0Uj+Uz3BA==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``
* URL: http://host.docker.internal:8001/cuenta/signup/
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/ ()(accept_privacy,csrfmiddlewaretoken,email,first_name,last_name,password1,password2,website)`
  * Method: `POST`
  * Parameter: `https://challenges.cloudflare.com/turnstile/v0/api.js`
  * Attack: ``
  * Evidence: `<script nonce="0GeLXm1z6ERYcE53+DxNHA==" src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`
  * Other Info: ``

Instances: Systemic


### Solution

Ensure JavaScript source files are loaded from only trusted sources, and the sources can't be controlled by end users of the application.

### Reference



#### CWE Id: [ 829 ](https://cwe.mitre.org/data/definitions/829.html)


#### WASC Id: 15

#### Source ID: 3

### [ Cross-Origin-Embedder-Policy Header Missing or Invalid ](https://www.zaproxy.org/docs/alerts/90004/)



##### Low (Medium)

### Description

Cross-Origin-Embedder-Policy header is a response header that prevents a document from loading any cross-origin resources that don't explicitly grant the document permission (using CORP or CORS).

* URL: http://host.docker.internal:8001
  * Node Name: `http://host.docker.internal:8001`
  * Method: `GET`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/
  * Node Name: `http://host.docker.internal:8001/`
  * Method: `GET`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/creditos-imagenes/
  * Node Name: `http://host.docker.internal:8001/creditos-imagenes/`
  * Method: `GET`
  * Parameter: `Cross-Origin-Embedder-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``


Instances: 3

### Solution

Ensure that the application/web server sets the Cross-Origin-Embedder-Policy header appropriately, and that it sets the Cross-Origin-Embedder-Policy header to 'require-corp' for documents.
If possible, ensure that the end user uses a standards-compliant and modern web browser that supports the Cross-Origin-Embedder-Policy header (https://caniuse.com/mdn-http_headers_cross-origin-embedder-policy).

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy ](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 14

#### Source ID: 3

### [ Cross-Origin-Resource-Policy Header Missing or Invalid ](https://www.zaproxy.org/docs/alerts/90004/)



##### Low (Medium)

### Description

Cross-Origin-Resource-Policy header is an opt-in header designed to counter side-channels attacks like Spectre. Resource should be specifically set as shareable amongst different origins.

* URL: http://host.docker.internal:8001/static/css/tailwind.css
  * Node Name: `http://host.docker.internal:8001/static/css/tailwind.css`
  * Method: `GET`
  * Parameter: `Cross-Origin-Resource-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/img/favicon.svg
  * Node Name: `http://host.docker.internal:8001/static/img/favicon.svg`
  * Method: `GET`
  * Parameter: `Cross-Origin-Resource-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/img/productos/playstation-5.webp
  * Node Name: `http://host.docker.internal:8001/static/img/productos/playstation-5.webp`
  * Method: `GET`
  * Parameter: `Cross-Origin-Resource-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/js/app.js
  * Node Name: `http://host.docker.internal:8001/static/js/app.js`
  * Method: `GET`
  * Parameter: `Cross-Origin-Resource-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/js/theme.js
  * Node Name: `http://host.docker.internal:8001/static/js/theme.js`
  * Method: `GET`
  * Parameter: `Cross-Origin-Resource-Policy`
  * Attack: ``
  * Evidence: ``
  * Other Info: ``

Instances: Systemic


### Solution

Ensure that the application/web server sets the Cross-Origin-Resource-Policy header appropriately, and that it sets the Cross-Origin-Resource-Policy header to 'same-origin' for all web pages.
'same-site' is considered as less secured and should be avoided.
If resources must be shared, set the header to 'cross-origin'.
If possible, ensure that the end user uses a standards-compliant and modern web browser that supports the Cross-Origin-Resource-Policy header (https://caniuse.com/mdn-http_headers_cross-origin-resource-policy).

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy ](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 14

#### Source ID: 3

### [ Dangerous JS Functions ](https://www.zaproxy.org/docs/alerts/10110/)



##### Low (Low)

### Description

A dangerous JS function seems to be in use that would leave the site vulnerable.

* URL: http://host.docker.internal:8001/static/vendor/htmx/htmx.min.js
  * Node Name: `http://host.docker.internal:8001/static/vendor/htmx/htmx.min.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `eval(`
  * Other Info: ``


Instances: 1

### Solution

See the references for security advice on the use of these functions.

### Reference


* [ https://v17.angular.io/guide/security ](https://v17.angular.io/guide/security)


#### CWE Id: [ 749 ](https://cwe.mitre.org/data/definitions/749.html)


#### Source ID: 3

### [ Permissions Policy Header Not Set ](https://www.zaproxy.org/docs/alerts/10063/)



##### Low (Medium)

### Description

Permissions Policy Header is an added layer of security that helps to restrict from unauthorized access or usage of browser/client features by web resources. This policy ensures the user privacy by limiting or specifying the features of the browsers can be used by the web resources. Permissions Policy provides a set of standard HTTP headers that allow website owners to limit which features of browsers can be used by the page such as camera, microphone, location, full screen etc.

* URL: http://host.docker.internal:8001/static/js/app.js
  * Node Name: `http://host.docker.internal:8001/static/js/app.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/js/carousel.js
  * Node Name: `http://host.docker.internal:8001/static/js/carousel.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/js/theme.js
  * Node Name: `http://host.docker.internal:8001/static/js/theme.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/vendor/alpine/alpine-csp.min.js
  * Node Name: `http://host.docker.internal:8001/static/vendor/alpine/alpine-csp.min.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``
* URL: http://host.docker.internal:8001/static/vendor/htmx/htmx.min.js
  * Node Name: `http://host.docker.internal:8001/static/vendor/htmx/htmx.min.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: ``


Instances: 5

### Solution

Ensure that your web server, application server, load balancer, etc. is configured to set the Permissions-Policy header.

### Reference


* [ https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy ](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy)
* [ https://developer.chrome.com/blog/feature-policy/ ](https://developer.chrome.com/blog/feature-policy/)
* [ https://scotthelme.co.uk/a-new-security-header-feature-policy/ ](https://scotthelme.co.uk/a-new-security-header-feature-policy/)
* [ https://w3c.github.io/webappsec-feature-policy/ ](https://w3c.github.io/webappsec-feature-policy/)
* [ https://www.smashingmagazine.com/2018/12/feature-policy/ ](https://www.smashingmagazine.com/2018/12/feature-policy/)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ Server Leaks Version Information via "Server" HTTP Response Header Field ](https://www.zaproxy.org/docs/alerts/10036/)



##### Low (High)

### Description

The web/application server is leaking version information via the "Server" HTTP response header. Access to such information may facilitate attackers identifying other vulnerabilities your web/application server is subject to.

* URL: http://host.docker.internal:8001/devolucion/
  * Node Name: `http://host.docker.internal:8001/devolucion/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `WSGIServer/0.2 CPython/3.12.10`
  * Other Info: ``
* URL: http://host.docker.internal:8001/factura/
  * Node Name: `http://host.docker.internal:8001/factura/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `WSGIServer/0.2 CPython/3.12.10`
  * Other Info: ``
* URL: http://host.docker.internal:8001/responder/
  * Node Name: `http://host.docker.internal:8001/responder/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `WSGIServer/0.2 CPython/3.12.10`
  * Other Info: ``
* URL: http://host.docker.internal:8001/robots.txt
  * Node Name: `http://host.docker.internal:8001/robots.txt`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `WSGIServer/0.2 CPython/3.12.10`
  * Other Info: ``
* URL: http://host.docker.internal:8001/sitemap.xml
  * Node Name: `http://host.docker.internal:8001/sitemap.xml`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `WSGIServer/0.2 CPython/3.12.10`
  * Other Info: ``

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is configured to suppress the "Server" header or provide generic details.

### Reference


* [ https://httpd.apache.org/docs/current/mod/core.html#servertokens ](https://httpd.apache.org/docs/current/mod/core.html#servertokens)
* [ https://learn.microsoft.com/en-us/previous-versions/msp-n-p/ff648552(v=pandp.10) ](https://learn.microsoft.com/en-us/previous-versions/msp-n-p/ff648552(v=pandp.10))
* [ https://www.troyhunt.com/shhh-dont-let-your-response-headers/ ](https://www.troyhunt.com/shhh-dont-let-your-response-headers/)


#### CWE Id: [ 497 ](https://cwe.mitre.org/data/definitions/497.html)


#### WASC Id: 13

#### Source ID: 3

### [ X-Content-Type-Options Header Missing ](https://www.zaproxy.org/docs/alerts/10021/)



##### Low (Medium)

### Description

The Anti-MIME-Sniffing header X-Content-Type-Options was not set to 'nosniff'. This allows older versions of Internet Explorer and Chrome to perform MIME-sniffing on the response body, potentially causing the response body to be interpreted and displayed as a content type other than the declared content type. Current (early 2014) and legacy versions of Firefox will use the declared content type (if one is set), rather than performing MIME-sniffing.

* URL: http://host.docker.internal:8001/static/css/tailwind.css
  * Node Name: `http://host.docker.internal:8001/static/css/tailwind.css`
  * Method: `GET`
  * Parameter: `x-content-type-options`
  * Attack: ``
  * Evidence: ``
  * Other Info: `This issue still applies to error type pages (401, 403, 500, etc.) as those pages are often still affected by injection issues, in which case there is still concern for browsers sniffing pages away from their actual content type.
At "High" threshold this scan rule will not alert on client or server error responses.`
* URL: http://host.docker.internal:8001/static/img/favicon.svg
  * Node Name: `http://host.docker.internal:8001/static/img/favicon.svg`
  * Method: `GET`
  * Parameter: `x-content-type-options`
  * Attack: ``
  * Evidence: ``
  * Other Info: `This issue still applies to error type pages (401, 403, 500, etc.) as those pages are often still affected by injection issues, in which case there is still concern for browsers sniffing pages away from their actual content type.
At "High" threshold this scan rule will not alert on client or server error responses.`
* URL: http://host.docker.internal:8001/static/img/productos/playstation-5.webp
  * Node Name: `http://host.docker.internal:8001/static/img/productos/playstation-5.webp`
  * Method: `GET`
  * Parameter: `x-content-type-options`
  * Attack: ``
  * Evidence: ``
  * Other Info: `This issue still applies to error type pages (401, 403, 500, etc.) as those pages are often still affected by injection issues, in which case there is still concern for browsers sniffing pages away from their actual content type.
At "High" threshold this scan rule will not alert on client or server error responses.`
* URL: http://host.docker.internal:8001/static/js/app.js
  * Node Name: `http://host.docker.internal:8001/static/js/app.js`
  * Method: `GET`
  * Parameter: `x-content-type-options`
  * Attack: ``
  * Evidence: ``
  * Other Info: `This issue still applies to error type pages (401, 403, 500, etc.) as those pages are often still affected by injection issues, in which case there is still concern for browsers sniffing pages away from their actual content type.
At "High" threshold this scan rule will not alert on client or server error responses.`
* URL: http://host.docker.internal:8001/static/js/theme.js
  * Node Name: `http://host.docker.internal:8001/static/js/theme.js`
  * Method: `GET`
  * Parameter: `x-content-type-options`
  * Attack: ``
  * Evidence: ``
  * Other Info: `This issue still applies to error type pages (401, 403, 500, etc.) as those pages are often still affected by injection issues, in which case there is still concern for browsers sniffing pages away from their actual content type.
At "High" threshold this scan rule will not alert on client or server error responses.`

Instances: Systemic


### Solution

Ensure that the application/web server sets the Content-Type header appropriately, and that it sets the X-Content-Type-Options header to 'nosniff' for all web pages.
If possible, ensure that the end user uses a standards-compliant and modern web browser that does not perform MIME-sniffing at all, or that can be directed by the web application/web server to not perform MIME-sniffing.

### Reference


* [ https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/compatibility/gg622941(v=vs.85) ](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/compatibility/gg622941(v=vs.85))
* [ https://owasp.org/www-community/Security_Headers ](https://owasp.org/www-community/Security_Headers)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ Authentication Request Identified ](https://www.zaproxy.org/docs/alerts/10111/)



##### Informational (High)

### Description

The given request has been identified as an authentication request. The 'Other Info' field contains a set of key=value lines which identify any relevant fields. If the request is in a context which has an Authentication Method set to "Auto-Detect" then this rule will change the authentication to match the request identified.

* URL: http://host.docker.internal:8001/cuenta/login/
  * Node Name: `http://host.docker.internal:8001/cuenta/login/ ()(csrfmiddlewaretoken,login,next,password,remember)`
  * Method: `POST`
  * Parameter: `login`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=login
userValue=foo-bar@example.com
passwordParam=password
referer=http://host.docker.internal:8001/cuenta/login/?next=/cuenta/retomas/
csrfToken=csrfmiddlewaretoken`
* URL: http://host.docker.internal:8001/cuenta/login/
  * Node Name: `http://host.docker.internal:8001/cuenta/login/ ()(csrfmiddlewaretoken,login,password,remember)`
  * Method: `POST`
  * Parameter: `login`
  * Attack: ``
  * Evidence: `password`
  * Other Info: `userParam=login
userValue=foo-bar@example.com
passwordParam=password
referer=http://host.docker.internal:8001/cuenta/login/
csrfToken=csrfmiddlewaretoken`


Instances: 2

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/auth-req-id/)



#### Source ID: 3

### [ Information Disclosure - Suspicious Comments ](https://www.zaproxy.org/docs/alerts/10027/)



##### Informational (Medium)

### Description

The response appears to contain suspicious comments which may help an attacker.

* URL: http://host.docker.internal:8001/static/js/carousel.js
  * Node Name: `http://host.docker.internal:8001/static/js/carousel.js`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `// when the user prefers reduced mot`
  * Other Info: `The following pattern was used: \bUSER\b and was detected 2 times, the first in likely comment: "// when the user prefers reduced motion. CSP-safe: no inline styles or eval.", see evidence field for the suspicious comment/snippet.`


Instances: 1

### Solution

Remove all comments that return information that may help an attacker and fix any underlying problems they refer to.

### Reference



#### CWE Id: [ 615 ](https://cwe.mitre.org/data/definitions/615.html)


#### WASC Id: 13

#### Source ID: 3

### [ Session Management Response Identified ](https://www.zaproxy.org/docs/alerts/10112/)



##### Informational (Medium)

### Description

The given response has been identified as containing a session management token. The 'Other Info' field contains a set of header tokens that can be used in the Header Based Session Management Method. If the request is in a context which has a Session Management Method set to "Auto-Detect" then this rule will change the session management to use the tokens identified.

* URL: http://host.docker.internal:8001
  * Node Name: `http://host.docker.internal:8001`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/
  * Node Name: `http://host.docker.internal:8001/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/buscar/%3Fq
  * Node Name: `http://host.docker.internal:8001/buscar/ (q)`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/carrito/
  * Node Name: `http://host.docker.internal:8001/carrito/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/comparar/
  * Node Name: `http://host.docker.internal:8001/comparar/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/creditos-imagenes/
  * Node Name: `http://host.docker.internal:8001/creditos-imagenes/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/cuenta/login/%3Fnext=/cuenta/retomas/
  * Node Name: `http://host.docker.internal:8001/cuenta/login/ (next)`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/legal/terminos/
  * Node Name: `http://host.docker.internal:8001/legal/terminos/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken`
* URL: http://host.docker.internal:8001/producto/mario-kart-world/
  * Node Name: `http://host.docker.internal:8001/producto/mario-kart-world/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken
cookie:sessionid`
* URL: http://host.docker.internal:8001/producto/playstation-vr2/
  * Node Name: `http://host.docker.internal:8001/producto/playstation-vr2/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken
cookie:sessionid`
* URL: http://host.docker.internal:8001/producto/timon-logitech-g29/
  * Node Name: `http://host.docker.internal:8001/producto/timon-logitech-g29/`
  * Method: `GET`
  * Parameter: `csrftoken`
  * Attack: ``
  * Evidence: `csrftoken`
  * Other Info: `cookie:csrftoken
cookie:sessionid`


Instances: 11

### Solution

This is an informational alert rather than a vulnerability and so there is nothing to fix.

### Reference


* [ https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-mgmt-id/ ](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-mgmt-id/)



#### Source ID: 3

### [ Storable and Cacheable Content ](https://www.zaproxy.org/docs/alerts/10049/)



##### Informational (Medium)

### Description

The response contents are storable by caching components such as proxy servers, and may be retrieved directly from the cache, rather than from the origin server by the caching servers, in response to similar requests from other users. If the response data is sensitive, personal or user-specific, this may result in sensitive information being leaked. In some cases, this may even result in a user gaining complete control of the session of another user, depending on the configuration of the caching components in use in their environment. This is primarily an issue where "shared" caching servers such as "proxy" caches are configured on the local network. This configuration is typically found in corporate or educational environments, for instance.

* URL: http://host.docker.internal:8001
  * Node Name: `http://host.docker.internal:8001`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://host.docker.internal:8001/
  * Node Name: `http://host.docker.internal:8001/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://host.docker.internal:8001/creditos-imagenes/
  * Node Name: `http://host.docker.internal:8001/creditos-imagenes/`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://host.docker.internal:8001/sitemap.xml
  * Node Name: `http://host.docker.internal:8001/sitemap.xml`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`
* URL: http://host.docker.internal:8001/static/img/favicon.svg
  * Node Name: `http://host.docker.internal:8001/static/img/favicon.svg`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: ``
  * Other Info: `In the absence of an explicitly specified caching lifetime directive in the response, a liberal lifetime heuristic of 1 year was assumed. This is permitted by rfc7234.`

Instances: Systemic


### Solution

Validate that the response does not contain sensitive, personal or user-specific information. If it does, consider the use of the following HTTP response headers, to limit, or prevent the content being stored and retrieved from the cache by another user:
Cache-Control: no-cache, no-store, must-revalidate, private
Pragma: no-cache
Expires: 0
This configuration directs both HTTP 1.0 and HTTP 1.1 compliant caching servers to not store the response, and to not retrieve the response (without validation) from the cache, in response to a similar request.

### Reference


* [ https://datatracker.ietf.org/doc/html/rfc7234 ](https://datatracker.ietf.org/doc/html/rfc7234)
* [ https://datatracker.ietf.org/doc/html/rfc7231 ](https://datatracker.ietf.org/doc/html/rfc7231)
* [ https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html ](https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)


#### CWE Id: [ 524 ](https://cwe.mitre.org/data/definitions/524.html)


#### WASC Id: 13

#### Source ID: 3

### [ User Controllable HTML Element Attribute (Potential XSS) ](https://www.zaproxy.org/docs/alerts/10031/)



##### Informational (Low)

### Description

This check looks at user-supplied input in query string parameters and POST data to identify where certain HTML attribute values might be controlled. This provides hot-spot detection for XSS (cross-site scripting) that will require further review by a security analyst to determine exploitability.

* URL: http://host.docker.internal:8001/buscar/%3Fcondicion=nuevo&disponible=on&marca=asus&orden=relevancia&plataforma=ps5&precio_max=0&precio_min=0&tipo=accessory
  * Node Name: `http://host.docker.internal:8001/buscar/ (condicion,disponible,marca,orden,plataforma,precio_max,precio_min,tipo)`
  * Method: `GET`
  * Parameter: `disponible`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/buscar/?condicion=nuevo&disponible=on&marca=asus&orden=relevancia&plataforma=ps5&precio_max=0&precio_min=0&tipo=accessory

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
disponible=on

The user-controlled value was:
on`
* URL: http://host.docker.internal:8001/buscar/%3Fcondicion=nuevo&disponible=on&marca=asus&orden=relevancia&plataforma=ps5&precio_max=0&precio_min=0&tipo=accessory
  * Node Name: `http://host.docker.internal:8001/buscar/ (condicion,disponible,marca,orden,plataforma,precio_max,precio_min,tipo)`
  * Method: `GET`
  * Parameter: `orden`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/buscar/?condicion=nuevo&disponible=on&marca=asus&orden=relevancia&plataforma=ps5&precio_max=0&precio_min=0&tipo=accessory

appears to include user input in:
a(n) [option] tag [value] attribute

The user input found was:
orden=relevancia

The user-controlled value was:
relevancia`
* URL: http://host.docker.internal:8001/catalogo/%3Fplataforma=ps5
  * Node Name: `http://host.docker.internal:8001/catalogo/ (plataforma)`
  * Method: `GET`
  * Parameter: `plataforma`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/catalogo/?plataforma=ps5

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
plataforma=ps5

The user-controlled value was:
ps5`
* URL: http://host.docker.internal:8001/catalogo/%3Ftipo=console
  * Node Name: `http://host.docker.internal:8001/catalogo/ (tipo)`
  * Method: `GET`
  * Parameter: `tipo`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/catalogo/?tipo=console

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
tipo=console

The user-controlled value was:
console`
* URL: http://host.docker.internal:8001/cuenta/login/%3Fnext=/cuenta/retomas/
  * Node Name: `http://host.docker.internal:8001/cuenta/login/ (next)`
  * Method: `GET`
  * Parameter: `next`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/cuenta/login/?next=/cuenta/retomas/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
next=/cuenta/retomas/

The user-controlled value was:
/cuenta/retomas/`
* URL: http://host.docker.internal:8001/cuenta/signup/%3Fnext=%252Fcuenta%252Fretomas%252F
  * Node Name: `http://host.docker.internal:8001/cuenta/signup/ (next)`
  * Method: `GET`
  * Parameter: `next`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/cuenta/signup/?next=%2Fcuenta%2Fretomas%2F

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
next=/cuenta/retomas/

The user-controlled value was:
/cuenta/retomas/`
* URL: http://host.docker.internal:8001/producto/nintendo-switch-lite/%3Fsku=NSWLITE-COR-N
  * Node Name: `http://host.docker.internal:8001/producto/nintendo-switch-lite/ (sku)`
  * Method: `GET`
  * Parameter: `sku`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/producto/nintendo-switch-lite/?sku=NSWLITE-COR-N

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
sku=NSWLITE-COR-N

The user-controlled value was:
nswlite-cor-n`
* URL: http://host.docker.internal:8001/cuenta/login/
  * Node Name: `http://host.docker.internal:8001/cuenta/login/ ()(csrfmiddlewaretoken,login,next,password,remember)`
  * Method: `POST`
  * Parameter: `login`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/cuenta/login/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
login=foo-bar@example.com

The user-controlled value was:
foo-bar@example.com`
* URL: http://host.docker.internal:8001/cuenta/login/
  * Node Name: `http://host.docker.internal:8001/cuenta/login/ ()(csrfmiddlewaretoken,login,next,password,remember)`
  * Method: `POST`
  * Parameter: `next`
  * Attack: ``
  * Evidence: ``
  * Other Info: `User-controlled HTML attribute values were found. Try injecting special characters to see if XSS might be possible. The page at the following URL:

http://host.docker.internal:8001/cuenta/login/

appears to include user input in:
a(n) [input] tag [value] attribute

The user input found was:
next=/cuenta/retomas/

The user-controlled value was:
/cuenta/retomas/`


Instances: 9

### Solution

Validate all input and sanitize output it before writing to any HTML attributes.

### Reference


* [ https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)


#### CWE Id: [ 20 ](https://cwe.mitre.org/data/definitions/20.html)


#### WASC Id: 20

#### Source ID: 3


