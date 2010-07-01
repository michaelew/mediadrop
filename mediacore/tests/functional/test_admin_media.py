import simplejson
import os
import pylons
from mediacore.tests import *
from mediacore.model import DBSession, Media, Author, fetch_row
from sqlalchemy.exc import SQLAlchemyError

class TestMediaController(TestController):
    def __init__(self, *args, **kwargs):
        TestController.__init__(self, *args, **kwargs)

        # Initialize pylons.app_globals, etc. for use in main thread.
        self.response = self.app.get('/_test_vars')
        pylons.app_globals._push_object(self.response.app_globals)
        pylons.config._push_object(self.response.config)

    def _login(self):
        test_user = 'admin'
        test_password = 'admin'
        login_form_url = url(controller='login', action='login')
        # Request, and fill out, the login form.
        login_page = self.app.get(login_form_url, status=200)
        login_page.form['login'] = test_user
        login_page.form['password'] = test_password
        # Submitting the login form should redirect us to the 'post_login' page
        login_handler_page = login_page.form.submit(status=302)

    def test_index(self):
        response = self.app.get(url(controller='admin/media', action='index'))
        # Test response...

    def test_add_new_media(self):
        new_url = url(controller='admin/media', action='edit', id='new')
        save_url = url(controller='admin/media', action='save', id='new')

        title = 'Add New Media Test'
        slug = 'add-new-media-test' # this should be unique
        name = 'Frederick Awesomeson'
        email = 'fake_address@mailinator.com'
        description = 'This media item was created to test the "admin/media/edit/new" method'
        htmlized_description = '<p>This media item was created to test the &quot;admin/media/edit/new&quot; method</p>'

        self._login()
        new_response = self.app.get(new_url, status=200)
        form = new_response.forms['media-form']
        form['title'] = title
        form['author_name'] = name
        form['author_email'] = email
        form['description'] = description
        # form['categories']
        # form['tags']
        form['notes'] = ''
        assert form.action == save_url

        save_response = form.submit()

        # Ensure that the correct redirect was issued
        assert save_response.status_int == 302
        media = fetch_row(Media, slug=slug)
        edit_url = url(controller='admin/media', action='edit', id=media.id)
        assert save_response.location == 'http://localhost%s' % edit_url

        # Ensure that the media object was correctly created
        assert media.title == title
        assert media.author.name == name
        assert media.author.email == email
        assert media.description == htmlized_description

        # Ensure that the edit form is correctly filled out
        edit_response = save_response.follow()
        form = edit_response.forms['media-form']
        assert form['title'].value == title
        assert form['author_name'].value == name
        assert form['author_email'].value == email
        assert form['slug'].value == slug
        assert form['description'].value == htmlized_description
        assert form['notes'].value == ''

    def test_edit_media(self):
        title = u'Edit Existing Media Test'
        slug = u'edit-existing-media-test' # this should be unique

        # Values that we will change during the edit process
        name = u'Frederick Awesomeson'
        email = u'fake_address@mailinator.com'
        description = u'This media item was created to test the "admin/media/edit/someID" method'
        htmlized_description = '<p>This media item was created to test the &quot;admin/media/edit/someID&quot; method</p>'
        notes = u'Some Notes!'

        try:
            media = self._new_publishable_media(slug, title)
            media.publishable = False
            media.reviewed = False
            DBSession.add(media)
            DBSession.commit()
            media_id = media.id
        except SQLAlchemyError, e:
            DBSession.rollback()
            raise e

        edit_url = url(controller='admin/media', action='edit', id=media_id)
        save_url = url(controller='admin/media', action='save', id=media_id)

        # render the edit form
        self._login()
        edit_response = self.app.get(edit_url, status=200)

        # ensure the form submits like we want it to
        form = edit_response.forms['media-form']
        assert form.action == save_url

        # Fill out the edit form, and submit it
        form['title'] = title
        form['author_name'] = name
        form['author_email'] = email
        form['description'] = description
        # form['categories']
        # form['tags']
        form['notes'] = notes
        save_response = form.submit()

        # Ensure that the correct redirect was issued
        assert save_response.status_int == 302
        assert save_response.location == 'http://localhost%s' % edit_url

        # Ensure that the media object was correctly updated
        media = fetch_row(Media, media_id)
        assert media.title == title
        assert media.slug == slug
        assert media.notes == notes
        assert media.description == htmlized_description
        assert media.author.name == name
        assert media.author.email == email

    def test_add_file(self):
        title = u'test-add-file'
        slug = u'Test Adding File on Media Edit Page.'

        try:
            media = self._new_publishable_media(slug, title)
            media.publishable = False
            media.reviewed = False
            DBSession.add(media)
            DBSession.commit()
            media_id = media.id
        except SQLAlchemyError, e:
            DBSession.rollback()
            raise e

        edit_url = url(controller='admin/media', action='edit', id=media_id)
        add_url = url(controller='admin/media', action='add_file', id=media_id)
        files = [
            ('file', '/some/fake/filename.mp3', 'FILE CONTENT: This is not an MP3 file at all, but this random string will work for our purposes.')
        ]
        fields = {
            'url': '',
        }
        # render the edit form
        self._login()
        edit_response = self.app.get(edit_url, status=200)

        # Ensure that the add-file-form rendered correctly.
        form = edit_response.forms['add-file-form']
        assert form.action == add_url
        for x in fields:
            form[x] = fields[x]
        form['file'] = files[0][1]

        # Submit the form with a regular POST request anyway, because
        # webtest.Form objects can't handle file uploads.
        add_response = self.app.post(add_url, params=fields, upload_files=files)
        assert add_response.status_int == 200
        assert add_response.headers['Content-Type'] == 'application/json'

        # Ensure the media file was created properly.
        media = fetch_row(Media, slug=slug)
        assert media.files[0].container == 'mp3'
        assert media.files[0].type == 'audio'
        assert media.type == 'audio'

        # Ensure that the response content was correct.
        add_json = simplejson.loads(add_response.body)
        assert add_json['success'] == True
        assert add_json['media_id'] == media_id
        assert add_json['file_id'] == media.files[0].id
        assert 'message' not in add_json

        # Ensure that the file was properly created.
        file_name = media.files[0].file_name
        file_path = os.sep.join((pylons.config['media_dir'], file_name))
        assert os.path.exists(file_path)
        file = open(file_path)
        content = file.read()
        file.close()
        assert content == files[0][2]
