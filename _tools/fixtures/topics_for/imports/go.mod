module corp.example.com/signin

go 1.22

// github.com/jcmturner/gokrb5/v8 was removed in the last release
require github.com/go-ldap/ldap/v3 v3.4.6

require (
	github.com/AzureAD/microsoft-authentication-library-for-go v1.2.0 // indirect
	golang.org/x/sys v0.20.0
)

replace golang.org/x/sys => golang.org/x/sys v0.19.0
