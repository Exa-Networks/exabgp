%{!?__python3:        %global __python3 /usr/bin/python3}
%{!?python3_sitelib:  %global python3_sitelib %(%{__python3} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%define version %(echo "$(python setup.py next)")

Name:           python-exabgp
Version:        %{version}
Release:        1%{?dist}
Summary:        The BGP swiss army knife of networking (Library)

Group:          Development/Libraries
License:        BSD
URL:            https://pypi.python.org/pypi/exabgp/
Source0:        https://github.com/Exa-Networks/exabgp/archive/%{version}/exabgp-%{version}.tar.gz
BuildArch:      noarch
Provides:       exabgp-libs

BuildRequires:  python-setuptools
Requires:       python3 >= 3.7

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
%{__python3} setup.py build

%install
%{__python3} setup.py install -O1 --root ${RPM_BUILD_ROOT}

# fix file locations
install bin/healthcheck ${RPM_BUILD_ROOT}%{_bindir}
mv ${RPM_BUILD_ROOT}%{_bindir} ${RPM_BUILD_ROOT}%{_sbindir}
mv ${RPM_BUILD_ROOT}%{_sbindir}/healthcheck ${RPM_BUILD_ROOT}/%{_sbindir}/exabgp-healthcheck
install -d -m 744 ${RPM_BUILD_ROOT}/%{_sysconfdir}/
install -d -m 755 ${RPM_BUILD_ROOT}/%{_sysconfdir}/exabgp/examples
install etc/exabgp/*.conf ${RPM_BUILD_ROOT}/%{_sysconfdir}/exabgp/examples

install -d %{buildroot}/%{_unitdir}
install etc/systemd/exabgp.service %{buildroot}/%{_unitdir}/
install etc/systemd/exabgp@.service %{buildroot}/%{_unitdir}/

install -d %{buildroot}/%{_mandir}/man1
install doc/man/exabgp.1 %{buildroot}/%{_mandir}/man1

install -d %{buildroot}/%{_mandir}/man5
install doc/man/exabgp.conf.5 %{buildroot}/%{_mandir}/man5

# Sample .conf
ln -s %{_sysconfdir}/exabgp/examples/api-api.conf %{buildroot}/%{_sysconfdir}/exabgp/exabgp.conf

%post -n exabgp
%systemd_post exabgp.service
# Default env
[ -f %{_sysconfdir}/exabgp/exabgp.env ] || %{_sbindir}/exabgp  > %{_sysconfdir}/exabgp/exabgp.env

%preun -n exabgp
%systemd_preun exabgp.service

%postun -n exabgp
%systemd_postun_with_restart exabgp.service

%files
%defattr(-,root,root,-)
%{python3_sitelib}/*
%doc COPYRIGHT CHANGELOG README.md

%files -n exabgp
%defattr(-,root,root,-)
%attr(755, root, root) %{_sbindir}/exabgp
%attr(755, root, root) %{_sbindir}/exabgpcli
%attr(755, root, root) %{_sbindir}/exabgp-healthcheck
%dir %{_sysconfdir}/exabgp
%{_sysconfdir}/exabgp/exabgp.conf
%dir %{_sysconfdir}/exabgp/examples
%attr(744, root, root) %{_prefix}/share/exabgp/*
%attr(744, root, root) %{_sysconfdir}/exabgp/examples/*
%{_unitdir}/exabgp.service
%{_unitdir}/exabgp@.service
%attr(644, root, root) %{_unitdir}/*
%doc COPYRIGHT CHANGELOG README.md
%{_mandir}/man1/*
%{_mandir}/man5/*

%changelog
* Tue Apr 24 2018 Thomas Mangin <thomas.mangin@exa-networks.co.uk> %{version}
- See https://github.com/Exa-Networks/exabgp/blob/%{version}/CHANGELOG
