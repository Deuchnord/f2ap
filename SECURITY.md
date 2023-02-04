# Security Policy

## Supported versions

f2ap versions follow the [semantic versioning](https://semver.org) standard.
Since it is at an early stage of development, its stability is not guaranteed until it reaches the version 1.0.0.
Until then, only the last version is supported for patches.

## How to inform my website visitors about security of f2ap?

If you use f2ap on your website, you can inform your visitors of the procedure to report any vulnerability by adding the following lines in your `/.well-known/security.txt` file:

```
# if you found a vulnerability on the ActivityPub implementation, please read the following document:
Contact: https://github.com/Deuchnord/f2ap/blob/main/SECURITY.md
```

> `/.well-known/security.txt` is a plain text file proposed on [RFC 9116](https://www.rfc-editor.org/rfc/rfc9116) that explains people who find a vulnerability on your website how to report it.
> If you don't have one yet, you should consider creating it with your own information.
> There is [a generator here](https://securitytxt.org) if you need help.

## Reporting a Vulnerability

If you have found a vulnerability on a website that uses f2ap, check first if you can reproduce it in the last public version.
If you can't, the website is most likely using an old version, so you should contact its administrator and tell them they should upgrade.

If you could reproduce on the last version, please don't open an issue directly, and send me an email to [security+f2ap@deuchnord.fr](mailto:security+f2ap@deuchnord.fr?subject=Vulnerability+in+f2ap) with the subject: _"Vulnerability in f2ap"_, and describe the exact nature of the vulnerability.
If you know how to fix the problem, you may attach your email with a Git patch to apply, so the security patch may be published more quickly.

For more security, you are encouraged to encrypt your email with the PGP public key found [here](https://deuchnord.fr/key.pgp).

Thank you for your time!
