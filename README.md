EasyBoxer : make label easy
# EasyBoxer : make label easy

## Introduce
+ Labeling image for yolov5 format
+ Just drag&drop to generate bounding box coordinate
+ EasyBoxer can edit coordinates easy
+ EasyBoxer can adjust brightness of image easy
+ EasyBoxer can remove file easy

## Note : EasyBoxer packaging by PyQt5 library
-> Only works on your local computer. Not works on colab or kaggle notebook

## Requirements
+ PyQt5
+ natsort
+ send2trash
+ numpy
+ cv2

```python
# install
!pip install PyQt5 natsort send2trash numpy opencv-python

# run
!python EasyBoxer.py
```

## Example
+ Just drag&drop to generate bounding box coordinate
+ EasyBoxer can edit coordinates easy   
-> Doubleclick coordinate to delete bounding box

![example1](https://user-images.githubusercontent.com/86835527/165117363-b7668e1f-cc23-43f1-bc26-70706ab2d716.gif)

+ EasyBoxer can adjust brightness of image easy   
-> No problem to detect object in darkness image   
(Note : It won't change original image)

![example2](https://user-images.githubusercontent.com/86835527/165120220-36046d8c-f5c1-4ff9-9b6e-07a8625e1d57.gif)

+ EasyBoxer can remove file easy   
(Note : Removing using send2trash library. So you can retore remove mistakes)

![example3](https://user-images.githubusercontent.com/86835527/165121442-390b258d-ca0d-4618-8e24-29a130b1044f.gif)
