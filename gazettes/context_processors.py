from gazettes.jurisdictions import jurisdiction_list


def jurisdictions(request):
    return {"jurisdictions": jurisdiction_list()}
