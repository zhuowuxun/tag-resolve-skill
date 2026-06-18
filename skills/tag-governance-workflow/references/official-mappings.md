# Official Mapping Notes

## Sources currently used in this project

- MITRE ATT&CK official dictionary: local synced ATT&CK data in `mitre_official_base`
- CAPEC official dictionary: CAPEC View 2000 / 658 synced into `mitre_official_base`
- CAPEC -> OWASP attacks: CAPEC View 659
- CWE official dictionary: MITRE CWE XML synced into `mitre_official_base`
- NIST official dictionary: NIST SP 800-53 Rev 5.2.0 OSCAL JSON synced into `mitre_official_base`

## High-confidence bridges

### Direct normalization
- `cwe_nocn` -> `official_cwe`
- `nist_control_nocn` -> `official_nist_controls`
- `mitre_techniques` -> `official_mitre_techniques`
- `mitre_tactics` -> `official_mitre_tactics`
- `ics_mitre_techniques` -> `official_ics_mitre_techniques`
- `ics_mitre_tactics` -> `official_ics_mitre_tactics`

### Parent supplementation
- `official_nist_controls` -> `official_nist_family`
- `official_mitre_techniques` -> `official_mitre_tactics`
- `official_ics_mitre_techniques` -> `official_ics_mitre_tactics`
- `official_capec_patterns` -> `official_capec_categories`

### CAPEC supplementation
Use this priority:
1. `official_cwe` -> `official_capec_patterns`
2. `official_mitre_techniques` / `official_ics_mitre_techniques` -> `official_capec_patterns`
3. then parent `official_capec_categories`

### OWASP supplementation
Use this priority:
1. CAPEC View 659 official mapping -> `official_owasp_attacks`
2. only then high-confidence project bridges
3. avoid broad heuristic expansion in workbook supplementation unless explicitly requested

## Things to avoid

- Do not assume CAPEC pattern/category is one-to-one.
- Do not assume ATT&CK -> CAPEC is official in the same sense as CAPEC View 659.
- Do not silently convert revoked ATT&CK techniques into active official codes without reporting it.
