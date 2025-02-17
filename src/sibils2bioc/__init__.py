from sibils2bioc.params import list_fields, flat_fields

def convert_to_BioC(sibils_doc,collection) :
    # returns a document in bioc format (for fetch or SIBiLS FTP files)
    bioc_doc = {"id":sibils_doc["_id"],
                    "infons":{},
                    "passages":[],
                    "relations":[]}
    
    # article infons: list_fields (medline or pmc specificities)
    if (collection == "pmc") :       
        # pmc authors and affiliations 
        for f in list_fields["pmc"] :
            names = []
            if (f in sibils_doc["document"] and sibils_doc["document"][f] is not None):
                for a in sibils_doc["document"][f] :
                    if (("name" in a) and (a["name"] not in names)) :
                        names.append(a["name"])
            bioc_doc["infons"][f] = ";".join(names)
        # pmc keywords
        if ("keywords" in sibils_doc["document"] and sibils_doc["document"]["keywords"] is not None) :
            bioc_doc["infons"]["keywords"] = ";".join(sibils_doc["document"]["keywords"])
    elif (collection == "medline") :
        # medline
        for f in list_fields["medline"] :
            names = []
            if (f in sibils_doc["document"] and sibils_doc["document"][f] is not None):
                for a in sibils_doc["document"][f] :
                    names.append(a)
            bioc_doc["infons"][f] = ";".join(names)
    
    # article infons: flat_fields (general case)
    for f in flat_fields[collection] :
        if (f in sibils_doc["document"]):
            bioc_doc["infons"][f] = sibils_doc["document"][f]

    # load annotations
    annotations_per_sentences = {}
    ia = 0
    for a in sibils_doc["annotations"] :
        annotation = {"id":str(ia),"infons":{}}
        ia += 1
        annotations_fields = ["type","concept_source","version","concept_id",
                           "preferred_term","nature",
                           "evidence_code","provenance","provider","score","attributes"]
        for f in annotations_fields :
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
        sentences_fields = ["field","tag","content_id","sentence_number","sentence_length"]
        for f in sentences_fields :
            if (f in s) :
                passage["infons"][f] = s[f]
        passage["infons"]["offset"] = offset
        offset += s["sentence_length"]
        passage["text"] = s["sentence"]
        passage["annotations"] = []
        if (s["sentence_number"] in annotations_per_sentences) :
            passage["annotations"] = annotations_per_sentences[s["sentence_number"]]
        bioc_doc["passages"].append(passage)

    # relations
    ir = 0
    if ("relations" in sibils_doc):
        for ta in sibils_doc["relations"] :
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
    return bioc_doc


