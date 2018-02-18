# strvup

Merge `gpx` and `hrm` files and upload to Strava in private mode.

Currently it extends GPS point with corresponding HR sample. Thus
resulting workout duration may be less than expected if is was started
without GPS lock.


# Set Up

To obtain API access, you need to create an app at
[Strava API application](https://www.strava.com/settings/api). Fill
all these fields at your taste except `Authorization Callback Domain`:
it should point to your machine with free IP port like
`localhost:1517`.

After that, create simple `oauth.json` file with the following content
(replace curly braces with actual data from the Strava App created above):

```
{
  "client_id": "{{ Client ID }}",
  "client_secret": "{{ Client Secret }}",
  "redirect_uri": "http://{{ Authorization Callback Domain }}/"
}
```

Now, on first upload (or when authorization is expired), your default web
browser will be launched to authorize `strvup` script. After successful
authorization, `oauth.json` file content will be updated with
authorization `token` data, so keep it writeable.
