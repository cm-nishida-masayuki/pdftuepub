def pdf_to_epub(data, context):
    from google.cloud import vision

    mime_type = 'application/pdf'
    batch_size = 2

    # get gcs uri from data
    bucket_name = data['bucket']
    output_bucket_name = f'{bucket_name}-outputs'
    file_name = data['name']

    gcs_input_uri = f'gs://{bucket_name}/{file_name}'
    gcs_output_uri = f'gs://{output_bucket_name}/{file_name}/'    

    client = vision.ImageAnnotatorClient()

    feature = vision.Feature(
        type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)

    # Input
    gcs_source = vision.GcsSource(uri=gcs_input_uri)
    input_config = vision.InputConfig(
        gcs_source=gcs_source, mime_type=mime_type)

    # Output
    gcs_destination = vision.GcsDestination(uri=gcs_output_uri)
    output_config = vision.OutputConfig(
        gcs_destination=gcs_destination, batch_size=batch_size)
    
    async_request = vision.AsyncAnnotateFileRequest(
        features=[feature], input_config=input_config,
        output_config=output_config
    )

    operation = client.async_batch_annotate_files(
        requests=[async_request]
    )

    operation.result(timeout=420)

    create_epub(output_bucket_name, file_name)

def create_epub(bucket, file_name):
    import json
    from google.cloud import storage
    from ebooklib import epub

    storage_client = storage.Client()

    prefix = f'{file_name}'

    output_bucket = storage_client.get_bucket(bucket)

    blob_list = [blob for blob in list(output_bucket.list_blobs(
        prefix=prefix
    )) if not blob.name.endswith('/')]

    book = epub.EpubBook()

    book.set_identifier('id123456')
    book.set_title(file_name)
    book.set_language('ja')

    book.add_author('Sample')

    page_no = 0
    first_chapter = None
    chpters = []
    for blob in blob_list:
        json_string = blob.download_as_string()
        ouptput = json.loads(json_string)

        for response in ouptput['responses']:
            page_no = page_no + 1
            annotation = response['fullTextAnnotation']
            chapter_file_name = f'chap_{page_no}.xhtml'
            chapter = epub.EpubHtml(title=f'Chapter{page_no}', file_name=chapter_file_name, lang='ja')
            chapter.content=u'<p>{}</p>'.format(annotation['text'])
            book.add_item(chapter)
            chpters.append(chapter)

            if not first_chapter:
                first_chapter = chapter

    book.toc = (epub.Link('chap_1.xhtml', 'Introduction', 'intro'),
                (epub.Section('Simple book'),
                chpters)
                )

    book.spine = ['nav', first_chapter]

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub_file_name = f'{file_name}.epub'
    epub_tmp_path = f'/tmp/{file_name}-{epub_file_name}'

    epub.write_epub(epub_tmp_path, book, {})

    epub_blob = output_bucket.blob(f'{file_name}/{epub_file_name}')
    epub_blob.upload_from_filename(epub_tmp_path)
