# Silexdata Cyberark Release Notes

**Topics**

- <a href="#v1-0-0">v1\.0\.0</a>
    - <a href="#release-summary">Release Summary</a>
    - <a href="#major-changes">Major Changes</a>
    - <a href="#new-plugins">New Plugins</a>
        - <a href="#lookup">Lookup</a>
    - <a href="#new-modules">New Modules</a>

<a id="v1-0-0"></a>
## v1\.0\.0

<a id="release-summary"></a>
### Release Summary

Initial release of the <code>silexdata\.cyberark</code> collection\, for retrieving credentials from CyberArk\'s Central Credential Provider \(CCP\)\.

<a id="major-changes"></a>
### Major Changes

* Initial release\. The <code>get\_pas\_object</code> lookup plugin\, and a module of the same name\, retrieve account properties such as the password from CyberArk CCP\'s AIM Web Service\, with optional client\-certificate authentication\. Both run on the controller\, so only the controller needs the <code>requests</code> library and network access to CCP\.

<a id="new-plugins"></a>
### New Plugins

<a id="lookup"></a>
#### Lookup

* silexdata\.cyberark\.get\_pas\_object \- Retrieve a credential from CyberArk Central Credential Provider \(CCP\)\.

<a id="new-modules"></a>
### New Modules

* silexdata\.cyberark\.get\_pas\_object \- Retrieve a credential from CyberArk Central Credential Provider \(CCP\)\.
