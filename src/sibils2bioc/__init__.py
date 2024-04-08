def convert_to_BioC(sibils_doc,collection) :
    # convert documents into BioC format (for fetch)
    bioc_doc = {"id":sibils_doc["_id"],
                    "infons":{},
                    "passages":[],
                    "relations":[]}
    # article infons
    if (collection == "pmc") :        
        list_fields = ["authors","affiliations"]
        for f in list_fields :
            names = []
            if (f in sibils_doc["document"] and sibils_doc["document"][f] is not None):
                for a in sibils_doc["document"][f] :
                    if (("name" in a) and (a["name"] not in names)) :
                        names.append(a["name"])
            bioc_doc["infons"][f] = ";".join(names)

        if ("keywords" in sibils_doc["document"] and sibils_doc["document"]["keywords"] is not None) :
            bioc_doc["infons"]["keywords"] = ";".join(sibils_doc["document"]["keywords"])
        
        flat_fields = ["article_type","language","medline_ta","journal",
                        "title","pmid","doi","archive_id","manuscript_id",
                        "pmcid","publication_date","pmc_release_date",
                        "pubyear","issue","volume","start_page","end_page",
                        "medline_pgn","abstract","licence","subset"]
        for f in flat_fields :
            bioc_doc["infons"][f] = sibils_doc["document"][f]
    
    elif (collection == "medline") :
        list_fields = ["authors","affiliations","mesh_terms","sup_mesh_terms","chemicals","publication_types","keywords"]
        for f in list_fields :
            names = []
            if (f in sibils_doc["document"] and sibils_doc["document"][f] is not None):
                for a in sibils_doc["document"][f] :
                    names.append(a)
            bioc_doc["infons"][f] = ";".join(names)
        
        flat_fields = ["title","abstract","coi_statement","journal","pubyear","entrez_date",
                        "pmid","pmcid","doi","medline_ta"]
        for f in flat_fields :
            bioc_doc["infons"][f] = sibils_doc["document"][f]
    
    elif (collection == "plazi") :    
        flat_fields = ["treatment_title","zenodo-doi","treatment-bank-uri","article-title","publication-doi","nomenclature-taxon-name"]
        for f in flat_fields :
            bioc_doc["infons"][f] = sibils_doc["document"][f]

    elif (collection == "suppdata") :
        flat_fields = ["ext","pmcid","filename",
                        "licence","title","publication_date","pmc_release_date","pubyear"]
        for f in flat_fields :
            bioc_doc["infons"][f] = sibils_doc["document"][f]

    # load annotations
    annotations_per_sentences = {}
    ia = 0
    for a in sibils_doc["annotations"] :
        annotation = {"id":str(ia),"infons":{}}
        ia += 1
        flat_fields = ["type","concept_source","version","concept_id","concept_form",
                        "preferred_term","nature","start_index","end_index",
                        "concept_length"]
        for f in flat_fields :
            if (f in a) :
                annotation["infons"][f] = a[f]
        annotation["text"] = a["concept_form"]
        annotation["locations"] = [{"offset": a["start_index"], "length": a["concept_length"]}]
        if (a["sentence_number"] not in annotations_per_sentences) :
            annotations_per_sentences[a["sentence_number"]] = []
        annotations_per_sentences[a["sentence_number"]].append(annotation)

    # sentences
    offset = 0
    for s in sibils_doc["sentences"] :
        passage = {"infons":{}}
        flat_fields = ["field","tag","content_id","sentence_number","sentence_length"]
        for f in flat_fields :
            if (f in s) :
                passage["infons"][f] = s[f]
        passage["infons"]["offset"] = offset
        offset += s["sentence_length"]
        passage["text"] = s["sentence"]
        passage["annotations"] = []
        if (s["sentence_number"] in annotations_per_sentences) :
            passage["annotations"] = annotations_per_sentences[s["sentence_number"]]
        bioc_doc["passages"].append(passage)

    # relation
    try :
        ir = 0
        for ta in sibils_doc["triple_annotations"] :
            for c1 in ta["concept1"] :
                for c2 in ta["concept2"] :
                    if (len(ta["concept3"]) == 0) :
                        relation = {"id":"R"+str(ir),"infons":{
                            "type":"biotic interaction",
                            },"nodes":[{"refid":str(c1),"role":"species1"},{"refid":str(c2),"role":"species2"}]}
                        bioc_doc["relations"].append(relation)
                        ir += 1
                    else :
                        for c3 in ta["concept3"] :
                            relation = {"id":"R"+str(ir),"infons":{
                                "type":"biotic interaction",
                                },"nodes":[{"refid":str(c1),"role":"species1"},{"refid":str(c2),"role":"species2"},{"refid":str(c3),"role":"interaction"}]}
                            bioc_doc["relations"].append(relation)
                            ir += 1
    except Exception as e :
        efile = open("bioc_errors.log","a",encoding="utf-8")
        efile.write(sibils_doc["_id"]+"\t"+str(e)+"\n")
        efile.close()
        pass

    return bioc_doc


