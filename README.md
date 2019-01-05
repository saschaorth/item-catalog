# item-catalog

A web application that provides a list of items within a variety of categories and 
an integrated third party user registration and authentication via google OAuth2.0. 
Authenticated users have the ability to post, edit, and delete their own items.

## Setup

- Install [Vagrant](https://www.vagrantup.com/) and [VirtualBox](https://www.virtualbox.org/).
- Clone the [fullstack-nanodegree-vm repository](https://github.com/udacity/fullstack-nanodegree-vm).
- Navigate into the vagrant directory with `cd fullstack-nanodegree-vm/vagrant/` and replace the catalog 
directory with this repositiory.

## How to run the application

- Launch the Vagrant VM from within the vagrant directory with:
`vagrant up`
- Enter the shell with: `vagrant ssh`
- Navigate to the catalog directory with: `cd /vagrant/catalog`
- In order to add items to a category you have to create the category first. 
You can create some test categories with: `python test_items.py`
- In order get the third party user registration via Google's OAuth2.0 started
[Create your own client secrets](https://developers.google.com/identity/protocols/OAuth2)
and save them as client_secrets in the catalog directory.
- Start the application with: `python application.py`
- Now access the application via: `http://localhost:5000/`