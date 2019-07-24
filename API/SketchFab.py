# -*- coding: utf-8 -*-
import arcpy
import requests
from time import sleep
from API.RetrievePasswords import Passwords


class SketchfabClient(object):

    def __init__(self):
        self._base_url = r'https://api.sketchfab.com/v3'
        self._headers = {r'Authorization': r'Token {}'.format(Passwords('SketchFab', 'svalbox'))}

    def post_model(self, data, model_path):
        """
        POST a model to Sketchfab's APIs.

        :param data: the data sent as x-www-form-encoded
        :type data: dict

        :param model_path: the full path of the model from ArcGIS
        :type model_path: str

        :returns: response from Sketchfab, only uid is interesting
        :rtype: dict
        """
        response = requests.post(self._base_url + r'/models',
                                 data=data,
                                 files={'modelFile': open(model_path, 'rb')},
                                 headers=self._headers)
        self.response = response.json()
        return response

    def check_upload(self, model_uid, width, height):
        params = {
            'url': r'https://sketchfab.com/models/' + model_uid,
            'maxwidth': width,
            'maxheight': height
        }
        try:
            arcpy.AddMessage('Checking whether model has been uploaded to SketchFab (at 1 minute intervals).')
            for i in range(30):
                response = self.embed_model(params)

                if 'detail' in response.json().keys():
                    arcpy.AddMessage("Not ready yet, trying again...")
                    sleep(60)
                    continue

                break

        except Exception as e:
            arcpy.AddMessage(u'An error occured: {}'.format(e))
            raise

        if int(response.status_code) not in [200, 201, 202]:
            raise requests.exceptions.HTTPError(str(response))
        arcpy.AddMessage('A corresponding model is available on SketchFab.') #and can be accessed here: https://sketchfab.com/3d-models/{}'.format{response['uid']})
        self.response = response.json()
        return response

    def embed_model(self, params):
        """
        GET the embed model HTML
        """
        response = requests.get(r'https://sketchfab.com/oembed',
                                params)

        return response

    def embed_modelSimple(self,model_uid, width, height):
        """
        Instead of using Sketchfab's Embed function, create our own little iframe.
        """
        arcpy.AddMessage(f'Embedding SketchFab model {model_uid} into simple HTML iframe')
        html = f'<iframe src=https://sketchfab.com/models/{model_uid}/embed width="{width}" height="{height}" ' \
            f'frameborder="0"></iframe>'
        return html

if __name__ == '__main__':
    A = SketchfabClient()
    # Mandatory parameters
    model_file = 'D:/DATABASE/VOM/20190709_PyramidenNW/20190709_PyramidenNW.zip'  # path to your model

    # Optional parameters
    name = 'Alic Bob model'
    description = 'This is a bob model I made with love and passion'
    # password = 'my-password'  # requires a pro account
    private = 0  # requires a pro account
    tags = ['bob', 'character', 'video-games']  # Array of tags
    categories = ['people']  # Array of categories slugs
    license = 'CC Attribution'  # License label
    isPublished = True,  # Model will be on draft instead of published
    isInspectable = True,  # Allow 2D view in model inspector

    data = {
        'name': name,
        'description': description,
        'tags': tags,
        'categories': categories,
        'license': license,
        'private': private,
        # 'password': password,
        'isPublished': isPublished,
        'isInspectable': isInspectable
    }
    A.response = A.post_model(data, model_file).json()
    arcpy.AddMessage(A.response)
    A.check_upload(A.response['uid'], 1000, 750)