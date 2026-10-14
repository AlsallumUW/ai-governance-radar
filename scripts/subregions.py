"""UN M49 geoscheme subregions (intermediate regions for sub-Saharan Africa and Latin America), ISO3 -> subregion.
Used to suggest other countries at the end of a country page."""
_M49 = {
    "Northern Africa": "DZA EGY LBY MAR SDN TUN",
    "Eastern Africa": "BDI COM DJI ERI ETH KEN MDG MWI MUS MOZ RWA SYC SOM SSD TZA UGA ZMB ZWE",
    "Middle Africa": "AGO CMR CAF TCD COG COD GNQ GAB STP",
    "Southern Africa": "BWA SWZ LSO NAM ZAF",
    "Western Africa": "BEN BFA CPV CIV GMB GHA GIN GNB LBR MLI MRT NER NGA SEN SLE TGO",
    "Caribbean": "ATG BHS BRB CUB DMA DOM GRD HTI JAM KNA LCA VCT TTO",
    "Central America": "BLZ CRI SLV GTM HND MEX NIC PAN",
    "South America": "ARG BOL BRA CHL COL ECU GUY PRY PER SUR URY VEN",
    "Northern America": "CAN USA",
    "Central Asia": "KAZ KGZ TJK TKM UZB",
    "Eastern Asia": "CHN JPN MNG PRK KOR",
    "South-eastern Asia": "BRN KHM IDN LAO MYS MMR PHL SGP THA TLS VNM",
    "Southern Asia": "AFG BGD BTN IND IRN MDV NPL PAK LKA",
    "Western Asia": "ARM AZE BHR CYP GEO IRQ ISR JOR KWT LBN OMN QAT SAU PSE SYR TUR ARE YEM",
    "Eastern Europe": "BLR BGR CZE HUN POL MDA ROU RUS SVK UKR",
    "Northern Europe": "DNK EST FIN ISL IRL LVA LTU NOR SWE GBR",
    "Southern Europe": "ALB AND BIH HRV GRC VAT ITA MLT MNE MKD PRT SMR SRB SVN ESP",
    "Western Europe": "AUT BEL FRA DEU LIE LUX MCO NLD CHE",
    "Australia and New Zealand": "AUS NZL",
    "Melanesia": "FJI PNG SLB VUT",
    "Micronesia": "KIR MHL FSM NRU PLW",
    "Polynesia": "WSM TON TUV",
}
SUBREGION = {iso: name for name, isos in _M49.items() for iso in isos.split()}
