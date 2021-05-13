import urllib.request
import urllib.error
import sys
from xml.dom import minidom


# ogólna funkcja do przekazywania danych do poszczególnych funkcji obrabiających je
def get_xml(url):
    with urllib.request.urlopen(url) as f:
        request = f.read().decode("utf-8")
    xml_data = minidom.parseString(request)
    return xml_data


# wydobywanie z danych imienia i nazwiska osoby, której identyfikator został podany
def get_name(xml):
    name = xml.getElementsByTagName("personal-details:given-names")[0].firstChild.data
    surname = xml.getElementsByTagName("personal-details:family-name")[0].firstChild.data
    return name + " " + surname + "\n"


# funkcja pozyskująca dane o pracy z bazy doi
def get_doi_data(doi_id):
    # sprawdzam czy dane można pozyskać
    try:
        req = urllib.request.Request(f"https://doi.org/{doi_id}")
        req.add_header("Accept", "application/rdf+xml")
        doi_data = get_xml(req)
    except urllib.error.URLError:
        return "Nie można pozyskać danych.\n"

    # przeglądając doi znalazłem dwa typy tagów, więc postanowiłem umieścić sprawdzenie, który z nich jest używany
    if doi_data.getElementsByTagName("rdf:RDF")[0].hasAttribute("xmlns:j.0"):
        tags = ["j.0", "j.2", "j.3"]
    elif doi_data.getElementsByTagName("rdf:RDF")[0].hasAttribute("xmlns:bibo"):
        tags = ["dc", "bibo", "foaf"]

    # dla każdej z danych: daty publikacji, tytułu magazynu/książki, wydawcy i autorów sprawdzam,
    # czy dane w ogóle zostały podane w pliku, jeśli nie, wypisuję, że brak takich danych
    try:
        date = doi_data.getElementsByTagName(f"{tags[0]}:date")[0].firstChild.data
    except (IndexError, AttributeError):
        date = "brak danych"

    try:
        with doi_data.getElementsByTagName(f"{tags[1]}:Journal")[0] as journal_info:
            journal_title = journal_info.getElementsByTagName(f"{tags[0]}:title")[0].firstChild.data
    except (IndexError, AttributeError):
        try:
            with doi_data.getElementsByTagName(f"{tags[1]}:Book")[0] as journal_info:
                journal_title = journal_info.getElementsByTagName(f"{tags[0]}:title")[0].firstChild.data
        except (IndexError, AttributeError):
            journal_title = "brak danych"

    try:
        journal_volume = doi_data.getElementsByTagName(f"{tags[1]}:volume")[0].firstChild.data
    except (IndexError, AttributeError):
        journal_volume = "brak danych"

    try:
        journal_publisher = doi_data.getElementsByTagName(f"{tags[0]}:publisher")[0].firstChild.data
    except (IndexError, AttributeError):
        journal_publisher = "brak danych"
    link = f"http://doi.org/{doi_id}"
    names_xml = doi_data.getElementsByTagName(f"{tags[2]}:name")
    names = ", ".join([names_xml[i].firstChild.data for i in range(len(names_xml))])
    # wprowadzam dane do stworzonego wcześniej szablonu
    output_string = f"Data publikacji: {date}\n" \
                    f"Czasopismo: {journal_title}, numer: {journal_volume}\n" \
                    f"Wydawca: {journal_publisher}\n" \
                    f"Autorzy: {names}\n"\
                    f"Link do pracy: {link}\n"
    return output_string


def get_arxiv_data(arxiv_id):
    # analogicznie jak dla doi sprawdzam, czy dane w ogóle da się pozyskać
    arxiv_id = arxiv_id.replace("arXiv:", "")
    try:
        arxiv_data = get_xml(f"http://export.arxiv.org/api/query?id_list={arxiv_id}")
    except urllib.error.HTTPError as e:
        output_string = "Nie można uzyskać danych"
        return output_string

    # z bazy arxiv wydobywam tylko datę publikacji i autorów, gdyż nic więcej interesującego tam nie ma
    try:
        date = arxiv_data.getElementsByTagName("published")[0].firstChild.data
    except (AttributeError, IndexError):
        date = "brak danych"
    link = f"https://arxiv.org/pdf/{arxiv_id}"
    names_xml = arxiv_data.getElementsByTagName("name")
    names = ", ".join([names_xml[i].firstChild.data for i in range(len(names_xml))])
    # wprowadzam dane do stworzonego szablonu
    output_string = f"Data publikacji: {date}\n" \
                    f"Autorzy: {names}\n"\
                    f"Link do pracy: {link}\n"
    return output_string


# funkcja ma na celu decydować, z której bazy danych wydobywać dane (o ile dla pracy podane są dwa id)
# funkcja prioryretyzuje bazę doi, gdyż jest w niej więcej informacji i dopiero jeśli nie ma w niej danych,
# to sięga po bazę arxiv
def get_data(ids):
    doi_data = ""
    arxiv_data = ""
    for id in ids:
        id_val = id.getElementsByTagName("common:external-id-value")[0].firstChild.data
        if id.getElementsByTagName("common:external-id-type")[0].firstChild.data == "doi":
            doi_data = get_doi_data(id_val)
        elif id.getElementsByTagName("common:external-id-type")[0].firstChild.data == "arxiv":
            arxiv_data = get_arxiv_data(id_val)
    if doi_data != "":
        return doi_data
    else:
        return arxiv_data


# funkcja wydziela z otrzymanych danych informacje o poszczególnych danych, następnie wywołuje funkcje wydobywające
# konkretne dane, dodaje tytuł pracy oraz id w bazie doi i/lub arxiv, a na koniec łączy wszystkie dane w jeden string
def get_works(xml):
    works = []
    # wydzielam z danych informacje o konkretnych pracach i iteruję po każdej z nich
    for work in xml.getElementsByTagName("work:work-summary"):
        # wydobywam z danych tytuł pracy
        title = work.getElementsByTagName("common:title")[0].firstChild.data
        title_string = "Tytuł: " + title + "\n"
        work_data = None
        doi_id = ""
        arxiv_id = ""
        # iteruję po kolejnych id przydzielonych pracy w poszukiwaniu id bazy doi lub arxiv, jeśli program znajdzie
        # takie id, to dodaje je do stringa
        for id in work.getElementsByTagName("common:external-id"):
            if id.getElementsByTagName("common:external-id-type")[0].firstChild.data in ["doi", "arxiv"]:
                if id.getElementsByTagName("common:external-id-type")[0].firstChild.data == "doi":
                    doi_id = "DOI: " + id.getElementsByTagName("common:external-id-value")[0].firstChild.data + "\n"
                elif id.getElementsByTagName("common:external-id-type")[0].firstChild.data == "arxiv":
                    arxiv_id = "ARXIV: " + id.getElementsByTagName("common:external-id-value")[0].firstChild.data + "\n"
        # wywołuję funkcję wydobywającą dokładne dane o pracy
        work_data = get_data(work.getElementsByTagName("common:external-id"))
        if work_data is None:
            work_data = ""
        # łączę dane o pracy w jeden string
        work_full = title_string + doi_id + arxiv_id + work_data
        works.append(work_full)

    return "\n".join(works)


# sprawdzam czy przy wywoływaniu programu podane zostały argumenty odpowiadające chęci zapisania informacji do pliku
# jeśli nie, to program domyślnie wypisuje je na ekran
bool_print = True
if len(sys.argv) > 1:
    try:
        if sys.argv[1] == "-o" and sys.argv[2].endswith(".txt"):
            bool_print = False
        else:
            raise ValueError
    except IndexError:
        print("Podano niewłaściwą liczbę argumentów. Przechodzę w domyślny tryb wypisywania na ekran.\n")
    except ValueError:
        print("Podano niewłaściwe argumenty. Przechodzę w domyślny tryb wypisywania na ekran.\n")

data = None
# proszę użytkownika o podanie szukanego id w bazie orcid, jeśli jest ono niepoprawne to użytkownik proszony jest
# o ponowne podanie id
while data is None:
    try:
        orcid_id = input("Podaj id szukanej osoby: ")
        data = get_xml(f'https://pub.orcid.org/{orcid_id}')
    except urllib.error.URLError:
        print("Nie znaleziono podanego identyfikatora. Spróbuj jeszcze raz.")

output = get_name(data) + "\n" + get_works(data)
if bool_print is True:
    print(output)

# zapisuję dane do pliku, o ile taki argument został podany
else:
    try:
        f = open(sys.argv[2], "w", encoding="utf-8")
        f.write(output)
    finally:
        f.close()
