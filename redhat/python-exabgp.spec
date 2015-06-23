%{!?__python2:        %global __python2 /usr/bin/python2}
%{!?python2_sitelib:  %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}

Name:           python-exabgp
Version:        3.4.11
Release:        1%{?dist}
Summary:        The BGP swiss army knife of networking (Library)

Group:          Development/Libraries
License:        BSD
URL:            http://pypi.python.org/pypi/exabgp/
Source0:        https://github.com/Exa-Networks/exabgp/archive/%{version}/exabgp-%{version}.tar.gz
BuildArch:      noarch
Provides:       exabgp-libs

BuildRequires:  python-setuptools
Requires:       python2 >= 2.6, python-ipaddr

%description
ExaBGP python module

%package -n exabgp
Summary:        The BGP swiss army knife of networking
Group:          Applications/Internet
BuildRequires:  systemd-units
Requires:       systemd, exabgp-libs == %{version}

%description -n exabgp
ExaBGP allows engineers to control their network from commodity servers. Think of it as Software Defined Networking using BGP by transforming BGP messages into friendly plain text or JSON.

It comes with an healthcheck application to help you monitor your daemons and withdraw dead ones from the network during failures/maintenances. A full lab explaining how to use it is available here.

Find what other users have done with it. Current documented use cases include DDOS mitigation, network visualisation, anycast, service high availability.

%prep
%setup -q -n exabgp-%{version}

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --root ${RPM_BUILD_ROOT}

# fix file locations
mv ${RPM_BUILD_ROOT}%{_bindir} ${RPM_BUILD_ROOT}%{_sbindir}
mv ${RPM_BUILD_ROOT}%{_sbindir}/healthcheck ${RPM_BUILD_ROOT}/%{_sbindir}/exabgp-healthcheck
install -d -m 744 ${RPM_BUILD_ROOT}/%{_sysconfdir}/
mv ${RPM_BUILD_ROOT}/usr/etc/exabgp ${RPM_BUILD_ROOT}/%{_sysconfdir}/

install -d %{buildroot}/%{_unitdir}
install etc/systemd/exabgp.service %{buildroot}/%{_unitdir}/

install -d %{buildroot}/%{_mandir}/man1
install doc/man/exabgp.1 %{buildroot}/%{_mandir}/man1

install -d %{buildroot}/%{_mandir}/man5
install doc/man/exabgp.conf.5 %{buildroot}/%{_mandir}/man5


%post -n exabgp
%systemd_post exabgp.service

%preun -n exabgp
%systemd_preun exabgp.service

%postun -n exabgp
%systemd_postun_with_restart exabgp.service

%files
%defattr(-,root,root,-)
%{python2_sitelib}/*
%doc COPYRIGHT CHANGELOG README.md

%files -n exabgp
%defattr(-,root,root,-)
%attr(755, root, root) %{_sbindir}/exabgp
%attr(755, root, root) %{_sbindir}/exabgp-healthcheck
%dir %{_sysconfdir}/exabgp
%attr(744, root, root) %{_sysconfdir}/exabgp/*
%{_unitdir}/exabgp.service
%doc COPYRIGHT CHANGELOG README.md
%{_mandir}/man1/*
%{_mandir}/man5/*

%changelog
* Tue Jun 09 2015 Arun Babu Neelicattu <arun.neelicattu@gmail.com> - 3.4.11-1
- Initial release

