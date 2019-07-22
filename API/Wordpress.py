import requests
import json
import base64
import os
import arcpy
import datetime
from API.RetrievePasswords import Passwords

class WordpressClient:
    def __init__(self):
        self.wordpress_authentication()

    def wordpress_authentication(self,user='arcgis',password=Passwords('Svalbox','arcgis'),url='https://svalbox.no/wp-json/wp/v2'):
        '''
        :param user: user for logging in to wordpress, default = arcgis
        :param password: password for logging in to wordpress, default = arcgis
        :param url: Svalbox site url
        :return:
        '''

        data_string = user + ':' + password
        self._token = base64.b64encode(data_string.encode())
        self.headers = {'Accept': 'application/json',
                        'Authorization': 'Basic {}'.format(self._token.decode('utf-8'))}
        self.url = url


    def create_wordpress_post(self, data, type='portfolio',publish=False,featured_media = None):
        '''

        :param data: dict with all required entries for the post
        :return:

        :publish: boolean for adding as draft (default, False) or post (True)

        :featured_media: if not None, takes the image ID
        :type: int
        '''

        data.update({'date': datetime.datetime.now().strftime('%y-%m-%dT%H:%M:%S')})
        self.payload = data
        self.payload['status'] = 'publish' if publish else 'draft'

        if featured_media is not None:
            self.payload.update({'featured_media':featured_media})

        self.headers['Content-Type'] = 'application/json'

        if type =='post':
            r = requests.post(self.url+'/posts', data=json.dumps(self.payload), headers=self.headers)

        elif type == 'portfolio':
            self.payload.update({'portfolio_categories':[22]})
            r = requests.post(self.url + '/portfolio', data=json.dumps(self.payload), headers=self.headers)


        response = json.loads(r.content)
        try:
            arcpy.AddMessage(response['link'])
        except:
            arcpy.AddMessage(response)
            arcpy.AddMessage('Have you tried checking the server .htaccess file for correct rule-rewriting?')
            raise

    def upload_worpress_media(self,file):
        '''
        :param file: media file to be uploaded to the wordpress site.
        :return:
        '''
        media = {'file': open(file, 'rb')}
        image = requests.post(self.url + '/media', headers=self.headers, files=media)
        self.imsrc = json.loads(image.content.decode('utf-8'))['link']
        self.imID = json.loads(image.content.decode('utf-8'))['id']

        self.media_params = {'Image':
                        {'path': file,
                         'name': os.path.basename(file),
                         'url':self.imsrc}}

        arcpy.AddMessage('Your image is published on ' + json.loads(image.content)['link'])

    def generate_html(self,iframe,
                modelname,
                description,
                model_info,
                model_specs
                ):
        '''
        :param modelname: Model name for the 3d model/locality
        :type modelname: str

        :param description: Text-base description of the 3d model/locality
        :type model_info: str

        :param model_info:  Information that populates the model_info part of the wiki-style table
        :type model_info: dict

        :param model_specs: Information that populates the model_specs part of the wiki-style table
        :type model_specs: dict

        :return:
        '''


        # Various html tables have been described here:
        SketchfabContent = '''
            <div class="container">
            <div class="sketchfab-embed-wrapper">
    
            {iframe}
            <p style="font-size: 13px; font-weight: normal; margin: 5px; color: #4a4a4a;"><a style="font-weight: bold; color: #1caad9;"</a></p>
    
            {description}
    
    
            </div>'''
        TableContentModel = '''
            <div class="floatRight">
            <table style="float: right; width: 258px; margin: 0 0 7px 14px; border-collapse: collapse; background: #fff; border: 1px solid #999; line-height: 1.5; color: #000; font-size: smaller;">
            <tbody>
            <tr>
            <th style="background: #ddd; border-bottom: 1px solid #999; font-size: larger; padding: 4px; text-align: center;" colspan="2"><span style="color: #333333;"><span style="font-weight: 400;">{modelname}</span></span></th>
            <tr>
            <th style="background: #ddd; border-bottom: 1px solid #999; border-top: 1px solid #999; padding: 4px; text-align: center;" colspan="2"><span style="color: #333333;"><span style="font-size: 14px; font-weight: 400;">{modelinformation}</span></span></th>
            </tr>
            '''
        TableContentSpecs = '''
            <tr>
            <th style="background: #ddd; border-bottom: 1px solid #999; border-top: 1px solid #999; padding: 4px; text-align: center;" colspan="2"><span style="color: #333333;"><span style="font-size: 14px; font-weight: 400;">{modelspecs}</span></span></th>
            </tr>
            '''
        ModelInfo = '''
            <tr style="border-bottom: 1px solid #999;">
            <td style="padding: 4px;"><span style="color: #333333;"><span style="font-size: 14px;">{descriptor}</span></span></td>
            <td style="padding: 4px;"><span style="color: #333333;"><span style="font-size: 14px;">{descriptor_txt}</span></span></td>
            </tr>
            '''
        ModelSpecs='''
            <tr style="border-bottom: 1px solid #999;">
            <td style="padding: 4px;"><span style="color: #333333;"><span style="font-size: 14px;">{descriptor}</span></span></td>
            <td style="padding: 4px;"><span style="color: #333333;"><span style="font-size: 14px;">{descriptor_txt}</span></span></td>
            </tr>
            '''
        Closing = '''
            </tbody>
            </table>
            </div>
            </div>
            '''
        arcpy.AddMessage(SketchfabContent)
        SketchfabContent = SketchfabContent.format(iframe=iframe, description=description)
        TableContentModel = TableContentModel.format(modelname=modelname, model_info=model_info)
        TableContentSpecs = TableContentSpecs.format(model_specs=model_specs)

        ModelInfoFilled = ''
        for key in ModelInfoContents:
            descriptor = key
            descriptor_txt = ModelInfoContents[key]
            ModelInfoFilled += ModelInfo.format(descriptor=descriptor, descriptor_txt=descriptor_txt)

        ModelSpecsFilled = ''
        for key in ModelSpecsContents:
            descriptor = key
            descriptor_txt = ModelSpecsContents[key]
            ModelSpecsFilled += ModelSpecs.format(descriptor=descriptor, descriptor_txt=descriptor_txt)

        WordPress.html = SketchfabContent + TableContentModel + ModelInfoFilled + TableContentSpecs + ModelSpecsFilled + Closing

if __name__ == '__main__':
    A = WordpressClient()

    A.upload_worpress_media(file = 'D:/temp/VIRTUAL OUTCROPS/2017_09_09_Billefjorden_Skansen/IMG_7835.JPG')
    A.create_wordpress_post(post,featured_media=A.imID)

    post = {'title': 'third REST API post',
            'slug': 'rest-api-1',
            'status': 'publish',
            'content': 'awesome',
            'author': '4',
            'excerpt': 'Exceptional post!',
            'format': 'standard',
            }
    A.create_wordpress_post(post)
    arcpy.AddMessage(A.media_params)