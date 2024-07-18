from bs4 import BeautifulSoup
import re 

def from_html_to_text(tag):
    tag=tag.encode("utf-8")
    soup = BeautifulSoup(tag, features="html.parser")
    for script in soup(["script", "style"]):
        script.extract()   
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

def trata_alternativas(texto):
    itens = re.findall(r"\{(.*?)\}", texto)
    alternativas=[]
    correcoes=[]
    for item in itens:
        alternativa=item.split('",')[0].split('"text": ')[1][1:]
        alternativas.append(alternativa)
        
        correcao=item.split('"isRightAnswer": ')[1].split(',')[0]
        correcoes.append(correcao)        
    return alternativas, correcoes
