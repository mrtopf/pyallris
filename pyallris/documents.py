# coding=utf-8
import requests
from lxml import etree, html
from lxml.cssselect import CSSSelector
import datetime
import pytz
from pytz import timezone
import time
import pytz
utc = pytz.utc

from base import RISParser
import re

body_re = re.compile("<?xml .*<body[ ]*>(.*)</body>") # find everything inside a body of a subdocument

class DocumentParser(RISParser):
    """"""

    # an easy way to get there selectors is to use firefox and copy the unique selector from the dev tools
    #
    #adoption_css = CSSSelector("#rismain table.risdeco tbody tr td table.tk1 tbody tr td table.tk1 tbody tr td table tbody tr.zl12 td.text3")
    #adoption_css = CSSSelector("table.risdeco tr td table.tk1 tr td.ko1 table.tk1 tr td table tr.zl12 td.text3")
    adoption_css = CSSSelector("tr.zl12:nth-child(3) > td:nth-child(5)") # selects the td which holds status information such as "beschlossen"
    top_css = CSSSelector("tr.zl12:nth-child(3) > td:nth-child(7) > form:nth-child(1) > input:nth-child(1)") # selects the td which holds the link to the TOP with transcript
    table_css = CSSSelector(".ko1 > table:nth-child(1)") # table with info block
    attachments_css = CSSSelector("table.tk1:nth-child(23)")
    #main_css = CSSSelector("#rismain table.risdeco")

    def __init__(self, url,
            tzinfo = timezone('Europe/Berlin'), 
            months = 12):
        self.utc = pytz.utc
        self.tzinfo = tzinfo
        super(DocumentParser, self).__init__(url)

        # this will be moved to the second stage
        self.db.documents.remove()

    def process(self):
        """process documents"""

        # get all the ids of the documents we need to parse
     
        agenda_items = self.db.agenda_items.find()
        document_ids = [item['volfdnr'] for item in agenda_items if "volfdnr" in item]
        #self.process_document("11066")
        self.process_document("11199") # this has attachments
        return
        for document_id in document_ids:
            self.process_document(document_id)
        return

    def process_document(self, document_id):
        """process a single document

        :param document_id: id of document to parse
        """
        url = self.url %document_id
        print url

        self.response = response = requests.get(url)
        doc = html.fromstring(response.text)

        # Beratungsfolge-Table checken
        table = self.table_css(doc)[0] # lets hope we always have this table
        data = {}
        for line in table:
            headline = line[0].text
            if headline:
                headline = headline.split(":")[0].lower()
                if headline == "betreff":
                    value = line[1].text_content().strip()
                    value = value.split("-->")[1] # there is some html comment with a script tag in front of the text which we remove
                    data[headline] = " ".join(value.split()) # remove all multiple spaces from the string
                elif headline in ['status', 'verfasser', u'federführend']:
                    data[headline] = line[1].text.strip()
                elif headline == "beratungsfolge":
                    data['consultation'] = self.process_consultation_list(line[1])
                    # we start of with a table inside the second td which has a first row of layout 1px images, so we ignore that
                # we simply ignore the rest (there might not be much more actually)
                #
        # the actual text comes after the table in a div but it's not valid XML or HTML this using regex
        docs = body_re.findall(self.response.text)
        data['docs'] = docs
        print len(docs)

        # get the attachments if possible
        attachments = self.attachments_css(doc)
        if len(attachments)>0 and attachments[0][1][0].text.strip() == "Anlagen:":
            for tr in attachments[0][3:]:
                nummer = tr[1].text
                link = tr[2][0]
                href = link.attrib["href"]
                name = link.text
                print nummer, name, href
            


        import pprint
        #pprint.pprint(data)
        print
        return

    def process_consultation_list(self, elem):
        """process the "Beratungsfolge" table in elem"""
        elem = elem[0]
        # the first line is pixel images, so skip it, then we need to jump in steps of two
        amount = (len(elem)-1)/2
        result = []
        i = 0
        item = None
        for line in elem:
            if i == 0:
                i=i+1
                continue

            # now we need to parse items which sometimes go over 2 lines. item == None means that we have line #1
            if item is None:

                # the order is "color/status", name of committee / link to TOP, more info
                status = line[0].attrib['title'].lower()
                item = {
                    'status'    : status,               # color coded status, like "Bereit", "Erledigt"
                    'committee' : line[1].text.strip(), # name of committee, e.g. "Finanzausschuss", unfort. without id
                    'action'    : line[2].text.strip(), # e.g. "Kenntnisnahme", "Entscheidung"
                }
                if status == "bereit": # here we don't have any further information
                    result.append(item)
                    item = None
            else:
                # this is about line 2 with lots of more stuff to process
                item['date'] = time.strptime(line[1].text.strip(), "%d.%m.%Y")
                form = line[2][0] # form with silfdnr and toplfdnr but only in link (action="to010.asp?topSelected=57023")
                item['silfdnr'] = form[0].attrib['value']
                item['meeting'] = line[3][0].text.strip()       # full name of meeting, e.g. "A/31/WP.16 öffentliche/nichtöffentliche Sitzung des Finanzausschusses"
                item['decision'] = line[4].text.strip()         # e.g. "ungeändert beschlossen"
                toplfdnr = None
                if len(line[6]) > 0:
                    form = line[6][0]
                    toplfdnr = form[0].attrib['value']
                item['toplfdnr'] = toplfdnr                     # actually the id of the transcript 
                result.append(item)
                item = None
            i=i+1
        return result
            

url = "http://ratsinfo.aachen.de/bi/vo020.asp?VOLFDNR=%s"
p = DocumentParser(url)
p.process()


