from glob import glob
import pathlib
from typing import Union, Sequence
import re 
from TexSoup import TexSoup
from pdf2image import convert_from_path
# Requires poppler system library
# !pip3 install pdf2image


def find_main_doc(folder: str) -> Union[str, Sequence[str]]:
    """ Attempt to find which TeX file is the main document 
    
    :param folder: folder containing the document
    :return: filename of the main document
    """
    
    texfiles = list(pathlib.Path(f"{folder}").glob("**/*.tex"))
    
    if (len(texfiles) == 1):
        return str(texfiles[0])

    print('multiple tex files')
    selected = None
    for e, fname in enumerate(texfiles):
        with open(fname, 'r', errors="surrogateescape") as finput:
            if 'documentclass' in finput.read():
                selected = e, fname
                break
    if selected is not None:
        print("Found main document in: ", selected[1])
        print(e, fname)
    else:
        raise RuntimeError('Could not locate the main document automatically.'
                           'Little help please!')
    return str(selected[1])


def convert_pdf_to_image(fname: str) -> str:
    """ Convert image from PDF to png
    The new image is stored with the original one
    
    :param fname: file to potentially convert
    """
    from pdf2image import convert_from_path
    pages = convert_from_path(fname, dpi=500)
    rootname = fname.replace('.pdf', '')
    if len(pages) > 1:
        for num, page in enumerate(pages, 1):
            page.save(f'{rootname}.{num:d}.png', 'PNG') 
        return f'{rootname}.*.png'
    else:
        pages[0].save(f'{rootname}.png', 'PNG')
        return f'{rootname}.png'
        

class LatexFigure(dict):
    """ Representation of a figure from a LatexDocument """
    def __init__(self, **data):
        super().__init__(data)
        self._check_pdf_figure()
    
    def _check_pdf_figure(self):
        """ Check if PDF images and convert to PNG if needed """
        images = self['images']
        new_images = []
        for image in images:
            if image[-4:] == '.pdf':
                new_images.append(convert_pdf_to_image(image))
            else:
                new_images.append(image)
        self['images'] = new_images
    
    def generate_markdown_text(self):
        if (len(self['images']) > 1):        
            width = 100 // len(self['images'])
            current = ''.join(
                [f'<img src="{figsub}" alt="Fig{num:d}.{sub:d}" width="{width}%"/>' 
                 for sub, figsub in enumerate(self['images'], 1)]
            )
        else:
            current = "![Fig{num:d}]({image})".format(num=self['num'], image=self['images'][0])

        return """|{current}|\n|---------|\n|**Figure {num}. -** {caption} (*{label}*)|""".format(current=current, **self)
    
    def _repr_markdown_(self):
        return Markdown(self.generate_markdown_text())._repr_markdown_()
    
    
def select_most_cited_figures(figures: Sequence[LatexFigure], 
                              content: dict, 
                              N: int = 3) -> Sequence[LatexFigure]:
    """ Finds the number of references to each figure and select the N most cited ones """
    # Find the number of references to each figure
    sorted_figures = sorted([(content.text.count(fig['label']), fig) for fig in figures], 
                            key=lambda x: x[0], reverse=True)
    selected_figures = [k[1] for k in sorted_figures[:N]]
    return selected_figures


class LatexDocument:
    """ Handles the latex document interface.
    
    Allows to extract title, authors, figures, abstract
    """
    def __init__(self, folder: str):
        self.main_file = find_main_doc(folder)
        self.folder = folder

        with open(self.main_file, 'r') as fin:
            main_tex = fin.read()
        self.content = TexSoup(main_tex)

    def get_all_figures(self) -> Sequence[LatexFigure]:
        """ Retrieve all figures (num, images, caption, label) from a document 

        :param content: the document content
        :return: sequence of LatexFigure objects
        """
        figures = self.content.find_all('figure')
        folder = self.folder
        data = []
        for num, fig in enumerate(figures, 1):
            num = num
            images = [f"{folder}/" + k.text[-1] for k in fig.find_all('includegraphics')]
            caption = [''.join(k.text) for k in fig.find_all('caption')][0].replace('~', ' ')
            label = [''.join(k.text) for k in fig.find_all('label')][0]
            fig = LatexFigure(num=num, images=images, caption=caption, label=label)
            data.append(fig)
        return data

    def get_abstract(self) -> str:
        """ Extract abstract from document """
        abstract = self.content.find_all('abstract')[0]
        abstract = [str(k).strip() for k in abstract if str(k)]
        abstract = [l.replace('~', ' ').replace('\n', '').strip() for l in abstract if l[0] != '%']
        abstract = ''.join(abstract)
        return abstract

    def get_title(self) -> str:
        """ Extract document's title """
        title = ''.join(self.content.find_all('title')[0].text)
        try:
            subtitle = ''.join(r.find_all('subtitle')[0].text)
            return ': '.join([title, subtitle])
        except:
            return title


    def get_authors(self) -> Sequence[str]:
        """ Get list of authors """
        authors = []
        for k in self.content.find_all('author')[0]:
            if str(k)[0] != '\\':
                authors.append(str(k)\
                                .replace('~', ' ')\
                                .replace(',', '')\
                                .strip())
        return authors
    
    def generate_markdown_text(self, with_figures:bool =True) -> str:
        """ Generate the markdown summary """
        latex_abstract = self.get_abstract()
        latex_title = self.get_title()
        latex_figures = self.get_all_figures()
        latex_authors = self.get_authors()
        joined_latex_authors = ', '.join(latex_authors)
        selected_latex_figures = select_most_cited_figures(latex_figures, self.content)
    
        text = f"""|    |\n|:---|\n| **{latex_title}**  |\n| {joined_latex_authors} |\n| {latex_abstract} |"""
        if with_figures:
            figures = '\n'.join([k.generate_markdown_text().replace('|---------|\n', '') 
                                 for k in selected_latex_figures])
            return text + '\n' + figures
        return text