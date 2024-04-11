list_fields = {"pmc": ["authors","affiliations"],
               "medline":["authors","affiliations","mesh_terms","sup_mesh_terms","chemicals","publication_types","keywords"]
              }

flat_fields = {"pmc":["article_type","language","medline_ta","journal","title","pmid","doi","archive_id","manuscript_id","pmcid","publication_date","pmc_release_date","pubyear","issue","volume","start_page","end_page","medline_pgn","abstract","licence","subset"],
               "medline":["title","abstract","coi_statement","journal","pubyear","entrez_date","pmid","pmcid","doi","medline_ta"],
               "plazi":["treatment_title","zenodo-doi","treatment-bank-uri","article-title","publication-doi","nomenclature-taxon-name"],
               "suppdata":["ext","pmcid","filename","licence","title","publication_date","pmc_release_date","pubyear"]
               }
